# dotfiles

## セットアップ方法

```
sudo pacman -S uv go-task
sudo ln -s /usr/bin/go-task /usr/local/bin/task

git clone git@github.com:wacky612/dotfiles.git
cd dotfiles

uv sync
task check
task deploy
```
