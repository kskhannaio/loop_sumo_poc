;;; export.el --- export the overview  -*- lexical-binding: t; -*-
;; Export simulation-overview.org to HTML (doc/index.html) or PDF.
;;   emacs --batch -l export.el -f overview-html
;;   emacs --batch -l export.el -f overview-pdf      (needs LaTeX)
(require 'ox-html) (require 'ox-latex)
(defun overview--open () (find-file (expand-file-name "simulation-overview.org" (file-name-directory load-file-name))))
(defvar overview--dir (file-name-directory load-file-name))
(defun overview-html ()
  (let ((org-html-doctype "html5") (org-html-html5-fancy t) (org-html-head-include-default-style nil)
        (org-html-head-include-scripts nil) (org-html-mathjax-template "") (org-html-validation-link nil)
        (org-html-postamble "Madiwala loop SUMO simulation &middot; %d")
        (org-html-head (concat "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                               "<link rel=\"stylesheet\" href=\"style.css\">")))
    (with-current-buffer (find-file-noselect (expand-file-name "simulation-overview.org" overview--dir))
      (org-export-to-file 'html (expand-file-name "index.html" overview--dir)))))
(defun overview-pdf ()
  (with-current-buffer (find-file-noselect (expand-file-name "simulation-overview.org" overview--dir))
    (org-latex-export-to-pdf)))
