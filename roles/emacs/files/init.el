(require 'package)
(add-to-list 'package-archives '("melpa" . "https://melpa.org/packages/") t)
(package-initialize)
(package-refresh-contents)

(package-install 'auto-complete)
(package-install 'haskell-mode)
(package-install 'yaml-mode)
(package-install 'js2-mode)
(package-install 'scss-mode)
(package-install 'markdown-mode)
(package-install 'lua-mode)

(define-key global-map "\C-h" 'delete-backward-char)
(setq make-backup-files nil)
(setq auto-save-default nil)
(global-linum-mode t)
(setq linum-format "%4d | ")
(show-paren-mode 1)
(setq kill-whole-line t)
(setq require-final-newline t)
(setq-default tab-width 4 indent-tabs-mode nil)
(setq custom-file (locate-user-emacs-file "custom.el"))
