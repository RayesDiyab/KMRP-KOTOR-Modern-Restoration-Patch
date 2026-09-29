#!/bin/zsh
# Double-click to install KMRP into KOTOR (Steam, macOS). See README.md.
cd "${0:A:h}/kmrp" || exit 1
xattr -dr com.apple.quarantine "${0:A:h}" 2>/dev/null
./kmrp-mac.sh install
rc=$?
print
read -k1 "?Press any key to close this window."
exit $rc
