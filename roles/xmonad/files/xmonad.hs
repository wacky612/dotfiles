import XMonad
import XMonad.Hooks.DynamicLog
import XMonad.Hooks.EwmhDesktops
import XMonad.Layout.NoBorders
import XMonad.Layout.Renamed
import XMonad.Util.Cursor
import XMonad.Util.EZConfig
import XMonad.Util.SpawnOnce
import System.Environment

join str1 str2 = str1 ++ " " ++ str2

blueColor = "#0000ff"
redColor = "#ff0000"

myLayout = smartBorders (Full ||| tall ||| mirror)
  where
    mirror  = renamed [Replace "Mirror Tile"] $ Mirror tiled
    tall    = renamed [Replace "Tile"] tiled
    tiled   = Tall nmaster delta ratio
    nmaster = 1
    ratio   = 1/2
    delta   = 3/100

myManageHook = composeAll
  [ className =? "feh" --> doFloat
  , className =? "mpv" --> doFloat
  ]

myStartupHook = do
  path <- io $ getEnv "PATH"
  home <- io $ getEnv "HOME"
  xdgRuntimeDir <- io $ getEnv "XDG_RUNTIME_DIR"
  io $ setEnv "LANG" "ja_JP.UTF-8"
  io $ setEnv "GTK_IM_MODULE" "uim"
  io $ setEnv "QT_IM_MODULE" "uim"
  io $ setEnv "XMODIFIERS" "@im=uim"
  io $ setEnv "LPASS_AGENT_TIMEOUT" "0"
  spawnOnce "cat $XDG_CONFIG_HOME/xresources/* | xrdb"
  setDefaultCursor xC_left_ptr
  spawnOnce "xset -b; xset -dpms; xset s off"
  spawnOnce "feh --no-fehbg --bg-scale \"$HOME/.wallpaper.png\""
  spawnOnce trayer
  spawnOnce "dunst"
  spawnOnce "uim-xim"
  spawnOnce "uim-toolbar-gtk-systray"
  spawnOnce "pasystray"
  spawnOnce "light-locker"
    where
      trayer = foldr1 join [ "trayer"            , "--edge top"
                           , "--align right"     , "--widthtype pixel"
                           , "--width 160"       , "--height 22"
                           , "--transparent true", "--alpha 0"
                           , "--tint 0x000000"
                           ]

main = do
  xConfig <- xmobar def { terminal           = "urxvt"
                        , focusFollowsMouse  = True
                        , borderWidth        = 1
                        , modMask            = mod4Mask
                        , workspaces         = map show [1..9]
                        , normalBorderColor  = blueColor
                        , focusedBorderColor = redColor
                        , layoutHook         = myLayout
                        , manageHook         = myManageHook
                        , startupHook        = myStartupHook
                        , handleEventHook    = fullscreenEventHook
                        }
  xmonad $ ewmh $ additionalKeysP xConfig [ ("M-p"  , spawn "dmenu_run -fn \"Ricty-12\"")
                                          , ("M-S-l", spawn "dm-tool lock")
                                          , ("M-S-/", spawn xprop)
                                          ]
    where
      xprop = foldr1 join [ "notify-send WM_CLASS \"$(xprop | grep WM_CLASS)\""
                          , "-i $HOME/.xmonad/x-icon.png"
                          ]
