#!/bin/zsh
# Double-click to remove KMRP from KOTOR and restore the original game files.
cd "${0:A:h}/kmrp" || exit 1
./kmrp-mac.sh uninstall
rc=$?
print
read -k1 "?Press any key to close this window."
exit $rc
