from __future__ import annotations

import copy
import json
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server import MCPServer

mcp = MCPServer("comfy")

BASE_URL     = os.environ.get("COMFYUI_URL", "http://localhost:8188").rstrip("/")
WORKFLOW_DIR = Path(os.environ.get("COMFY_WORKFLOW_DIR", Path(__file__).resolve().parent.parent / "workflows",))
OUTPUT_DIR   = Path(os.environ.get("COMFY_OUTPUT_DIR", Path.cwd() / "output",)).expanduser().resolve()
TIMEOUT_SECONDS = float(os.environ.get("COMFY_TIMEOUT", "600"))
POLL_SECONDS    = float(os.environ.get("COMFY_POLL_INTERVAL", "1"))

QWEN21_T2I_WORKFLOW        = WORKFLOW_DIR / "qwen21_t2i_heretic_api.json"
QWEN21_EDIT_WORKFLOW       = WORKFLOW_DIR / "qwen21_edit_heretic_api.json"
HUNYUAN3D21_I2M_WORKFLOW   = WORKFLOW_DIR / "hunyuan3d21_i2m_api.json"
HUNYUAN3D21_PAINT_WORKFLOW = WORKFLOW_DIR / "hunyuan3d21_paint_api.json"

def _load_workflow(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _seed(value: int | None) -> int:
    if value is None or value < 0:
        return random.SystemRandom().randrange(0, 2**63 - 1)
    return value


def _check_response(resp: httpx.Response) -> None:
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = resp.text[:2000]
        raise RuntimeError(f"ComfyUI HTTP {resp.status_code}: {detail}") from exc


def _queue(client: httpx.Client, workflow: dict[str, Any]) -> str:
    resp = client.post(f"{BASE_URL}/prompt", json={"prompt": workflow})
    _check_response(resp)
    data = resp.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI returned no prompt_id: {data}")
    return str(prompt_id)


def _wait(client: httpx.Client, prompt_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        resp = client.get(f"{BASE_URL}/history/{quote(prompt_id, safe='')}")
        _check_response(resp)
        data = resp.json()
        item = data.get(prompt_id)

        if item:
            status = item.get("status", {})

            if status.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI execution failed: {status}")

            if status.get("completed"):
                return item

        time.sleep(POLL_SECONDS)

    raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")


def _download_outputs(
    client: httpx.Client, history: dict[str, Any], prompt_id: str
) -> list[str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    for node_output in history.get("outputs", {}).values():
        for image in node_output.get("images", []):
            filename = image["filename"]
            subfolder = image.get("subfolder", "")
            image_type = image.get("type", "output")
            resp = client.get(
                f"{BASE_URL}/view",
                params={
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": image_type,
                },
            )
            _check_response(resp)
            suffix = Path(filename).suffix or ".png"
            target = OUTPUT_DIR / f"{prompt_id}_{len(paths) + 1}{suffix}"
            target.write_bytes(resp.content)
            paths.append(str(target))
    if not paths:
        raise RuntimeError("Workflow completed but no image output was found.")
    return paths


def _download_3d_outputs(
    client: httpx.Client, history: dict[str, Any], prompt_id: str
) -> list[str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    for node_output in history.get("outputs", {}).values():
        for item in node_output.get("3d", []):
            filename = item["filename"]
            subfolder = item.get("subfolder", "")
            file_type = item.get("type", "output")

            resp = client.get(
                f"{BASE_URL}/view",
                params={
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": file_type,
                },
            )
            _check_response(resp)

            suffix = Path(filename).suffix or ".glb"
            target = OUTPUT_DIR / f"{prompt_id}_{len(paths) + 1}{suffix}"
            target.write_bytes(resp.content)
            paths.append(str(target))

    if not paths:
        raise RuntimeError("Workflow completed but no 3D output was found.")

    return paths


def _download_temp_file(
    client: httpx.Client,
    filename: str,
    prompt_id: str,
) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    resp = client.get(
        f"{BASE_URL}/view",
        params={
            "filename": filename,
            "type": "temp",
        },
    )
    _check_response(resp)

    suffix = Path(filename).suffix
    target = OUTPUT_DIR / f"{prompt_id}{suffix}"
    target.write_bytes(resp.content)

    return str(target)


def _run(workflow: dict[str, Any]) -> tuple[str, list[str]]:
    with httpx.Client(timeout=httpx.Timeout(30.0, read=60.0)) as client:
        prompt_id = _queue(client, workflow)
        history = _wait(client, prompt_id)
        paths = _download_outputs(client, history, prompt_id)
    return prompt_id, paths


def _upload_input(client: httpx.Client, image_path: Path) -> str:
    if not image_path.is_file():
        raise FileNotFoundError(f"Input image does not exist: {image_path}")
    with image_path.open("rb") as f:
        resp = client.post(
            f"{BASE_URL}/upload/image",
            data={"overwrite": "true", "type": "input"},
            files={"image": (image_path.name, f, "application/octet-stream")},
        )
    _check_response(resp)
    data = resp.json()
    name = data.get("name")
    subfolder = data.get("subfolder", "")
    if not name:
        raise RuntimeError(f"Unexpected upload response: {data}")
    return f"{subfolder}/{name}" if subfolder else str(name)

@mcp.tool()
def unload_models() -> dict[str, Any]:
    """Unload models from ComfyUI and free cached GPU memory.

    Use this after image generation/editing when GPU VRAM is needed by another
    workload such as Hunyuan3D.
    """
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/free",
            json={
                "unload_models": True,
                "free_memory": True,
            },
        )
        _check_response(resp)

    return {
        "success": True,
        "message": "ComfyUI models unloaded and cached memory freed.",
    }

@mcp.tool()
def qwen21_generate_image(
    prompt: str,
    negative_prompt: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Generate an image with the fixed local Qwen-Image-2.1 NVFP4 workflow.

    Only prompt, negative_prompt and seed are variable. This tool never installs
    models or nodes and never modifies the workflow file on disk.
    """
    workflow = copy.deepcopy(_load_workflow(QWEN21_T2I_WORKFLOW))
    used_seed = _seed(seed)
    workflow["4"]["inputs"]["prompt"] = prompt
    workflow["4"]["inputs"]["negative_prompt"] = negative_prompt
    workflow["6"]["inputs"]["seed"] = used_seed
    prompt_id, paths = _run(workflow)
    return {
        "prompt_id": prompt_id,
        "seed": used_seed,
        "images": paths,
        "workflow": QWEN21_T2I_WORKFLOW.name,
    }


@mcp.tool()
def qwen21_edit_image(
    image_path: str,
    prompt: str,
    negative_prompt: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Edit one local image with the fixed Qwen-Image-2.1 NVFP4 workflow.

    The source image is uploaded to ComfyUI's input area. Only the input image,
    prompt, negative_prompt and seed are variable. No models/nodes are installed.
    """
    source = Path(image_path).expanduser().resolve()
    workflow = copy.deepcopy(_load_workflow(QWEN21_EDIT_WORKFLOW))
    used_seed = _seed(seed)

    with httpx.Client(timeout=httpx.Timeout(30.0, read=60.0)) as client:
        uploaded_name = _upload_input(client, source)
        workflow["10"]["inputs"]["image"] = uploaded_name
        workflow["4"]["inputs"]["prompt"] = prompt
        workflow["4"]["inputs"]["negative_prompt"] = negative_prompt
        workflow["6"]["inputs"]["seed"] = used_seed
        prompt_id = _queue(client, workflow)
        history = _wait(client, prompt_id)
        paths = _download_outputs(client, history, prompt_id)

    return {
        "prompt_id": prompt_id,
        "seed": used_seed,
        "source_image": str(source),
        "uploaded_as": uploaded_name,
        "images": paths,
        "workflow": QWEN21_EDIT_WORKFLOW.name,
    }


@mcp.tool()
def hunyuan3d21_generate_3d(
    image_path: str,
    seed: int | None = None,
) -> dict[str, Any]:
    """Generate a GLB mesh from one local image using Hunyuan3D 2.1.

    The source image is uploaded to ComfyUI and processed with the fixed
    Hunyuan3D 2.1 image-to-model workflow. Only the input image and seed
    are variable.
    """
    source = Path(image_path).expanduser().resolve()
    workflow = copy.deepcopy(_load_workflow(HUNYUAN3D21_I2M_WORKFLOW))
    used_seed = _seed(seed)

    with httpx.Client(timeout=httpx.Timeout(30.0, read=60.0)) as client:
        uploaded_name = _upload_input(client, source)

        workflow["1"]["inputs"]["image"] = uploaded_name
        workflow["7"]["inputs"]["seed"] = used_seed

        prompt_id = _queue(client, workflow)
        history = _wait(client, prompt_id)
        paths = _download_3d_outputs(client, history, prompt_id)

    return {
        "prompt_id": prompt_id,
        "seed": used_seed,
        "source_image": str(source),
        "uploaded_as": uploaded_name,
        "models": paths,
        "workflow": HUNYUAN3D21_I2M_WORKFLOW.name,
    }


@mcp.tool()
def hunyuan3d21_paint_3d(
    mesh_path: str,
    image_path: str,
    seed: int | None = None,
    view_size: int = 512,
    steps: int = 10,
    guidance_scale: float = 3.0,
    texture_size: int = 1024,
) -> dict[str, Any]:
    """Paint a local 3D mesh using Hunyuan3D 2.1 Paint PBR.

    The source mesh and reference image are uploaded to ComfyUI.
    The mesh is textured using the reference image and exported as a
    PBR GLB containing albedo and metallic-roughness materials.
    """
    mesh = Path(mesh_path).expanduser().resolve()
    image = Path(image_path).expanduser().resolve()

    if not mesh.is_file():
        raise FileNotFoundError(f"Input mesh does not exist: {mesh}")
    if not image.is_file():
        raise FileNotFoundError(f"Reference image does not exist: {image}")

    workflow = copy.deepcopy(_load_workflow(HUNYUAN3D21_PAINT_WORKFLOW))
    used_seed = _seed(seed)
    output_name = f"painted_{uuid.uuid4().hex[:12]}"

    with httpx.Client(timeout=httpx.Timeout(30.0, read=60.0)) as client:
        uploaded_mesh = _upload_input(client, mesh)
        uploaded_image = _upload_input(client, image)

        # LoadImage
        workflow["5"]["inputs"]["image"] = uploaded_image

        # MeshTools Load Mesh
        workflow["8"]["inputs"]["mesh_path"] = uploaded_mesh

        # Hunyuan3D 2.1 MultiViews Generator
        workflow["4"]["inputs"]["seed"] = used_seed
        workflow["4"]["inputs"]["view_size"] = view_size
        workflow["4"]["inputs"]["steps"] = steps
        workflow["4"]["inputs"]["guidance_scale"] = guidance_scale
        workflow["4"]["inputs"]["texture_size"] = texture_size

        # Hunyuan3D 2.1 InPaint
        workflow["7"]["inputs"]["output_mesh_name"] = output_name

        prompt_id = _queue(client, workflow)
        _wait(client, prompt_id)

        output_path = _download_temp_file(
            client,
            f"{output_name}.glb",
            prompt_id,
        )

    return {
        "prompt_id": prompt_id,
        "seed": used_seed,
        "source_mesh": str(mesh),
        "reference_image": str(image),
        "uploaded_mesh_as": uploaded_mesh,
        "uploaded_image_as": uploaded_image,
        "output_name": output_name,
        "models": [output_path],
        "workflow": HUNYUAN3D21_PAINT_WORKFLOW.name,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
