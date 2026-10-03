;;; init.el --- Emacs configuration -*- lexical-binding: t; -*-

;;; Package management

(require 'package)

;; GNU ELPA / NonGNU ELPA are configured by Emacs by default.
;; Add MELPA for packages that are not available there.
(add-to-list 'package-archives
             '("melpa" . "https://melpa.org/packages/")
             t)

;; `use-package' is built into recent Emacs.
(require 'use-package)
(require 'use-package-ensure)

;; Automatically install packages declared with `use-package'
;; if they are not installed yet.
(setq use-package-always-ensure t)


;;; Packages

(use-package auto-complete
  :defer t)

(use-package haskell-mode
  :defer t)

(use-package yaml-mode
  :mode "\\.ya?ml\\'")

(use-package js2-mode
  :mode "\\.js\\'")

(use-package scss-mode
  :mode "\\.scss\\'")

(use-package markdown-mode
  :mode (("\\.md\\'"       . markdown-mode)
         ("\\.markdown\\'" . markdown-mode)))

(use-package lua-mode
  :mode "\\.lua\\'")


;;; Language

(set-language-environment "Japanese")


;;; Key bindings

(global-set-key (kbd "C-h") #'delete-backward-char)


;;; Files

(setq make-backup-files nil
      auto-save-default nil
      require-final-newline t
      custom-file (locate-user-emacs-file "custom.el"))


;;; Editing

(setq kill-whole-line t)

(setq-default tab-width 4
              indent-tabs-mode nil)


;;; Display

(global-display-line-numbers-mode 1)
(show-paren-mode 1)


;;; init.el ends here
