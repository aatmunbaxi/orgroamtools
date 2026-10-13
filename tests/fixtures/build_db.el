;;; build_db.el --- Regenerate tests/fixtures/org-roam.db -*- lexical-binding: t; -*-

;; Usage (from the repository root):
;;   nix develop .#fixtures --command emacs --batch -l tests/fixtures/build_db.el
;;
;; Indexes tests/fixtures/roam/ with org-roam, then rewrites the absolute paths
;; org-roam stores into paths relative to tests/fixtures/roam/, so the database
;; can be committed. tests/conftest.py makes them absolute again at test time.

;;; Code:

(require 'org-roam)

(let* ((here (file-name-directory (or load-file-name buffer-file-name)))
       (org-roam-directory (file-name-as-directory (expand-file-name "roam" here)))
       (org-roam-db-location (expand-file-name "org-roam.db" here))
       (org-roam-db-update-on-save nil))
  (when (file-exists-p org-roam-db-location)
    (delete-file org-roam-db-location))
  (org-roam-db-sync)
  (org-roam-db--close-all)

  (let ((db (sqlite-open org-roam-db-location)))
    (dolist (stmt '("UPDATE nodes SET file = replace(file, ?1, ''), properties = replace(properties, ?1, '')"
                    "UPDATE files SET file = replace(file, ?1, '')"))
      (sqlite-execute db stmt (list org-roam-directory)))
    (sqlite-execute db "VACUUM")
    (sqlite-close db))
  (message "Wrote %s" org-roam-db-location))

;;; build_db.el ends here
