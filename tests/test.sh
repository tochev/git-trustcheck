#!/bin/bash
set -e
set -x

# NOTE: this script changes $HOME

# not very good but still something
    
echo $SCRIPT_DIR

#### functions
function get_key {
    gpg --with-colons --list-keys "$1" | head -n 2 | awk -F : '{print $5}' | tail -n 1
}

function assert {
    grep -q "$@" || exit 1 #bash
}

function gpg_fix_trust {
    gpg --list-keys --with-colons --fingerprint | \
        grep fpr | awk -F : '{print $10 ":6"}' | \
        gpg --import-ownertrust
}

function generate_gpg_keys {
    mkdir d1 && GNUPGHOME=$PWD/d1 gpg --gen-key --batch "$SCRIPT_DIR"/fixtures/key_gen.txt && GNUPGHOME=$PWD/d1 gpg --export-secret-keys --armor > "$SCRIPT_DIR"/fixtures/gpg_keys.gpg
    mkdir d2 && GNUPGHOME=$PWD/d2 gpg --gen-key --batch "$SCRIPT_DIR"/fixtures/unknown_key_gen.txt && GNUPGHOME=$PWD/d2 gpg --export-secret-keys --armor > "$SCRIPT_DIR"/fixtures/unknown_gpg_keys.gpg
}

#### end functions


#### SETUP
export SCRIPT_DIR="$(readlink -f $(dirname $0))"
rm -rf testground
mkdir -p testground/home2 && cd testground
export TESTGROUND="$PWD"
ln -s "$SCRIPT_DIR"/../git_trustcheck.py git-trustcheck
export PATH="$TESTGROUND":"$PATH"
export HOME="$TESTGROUND"
unset GNUPGHOME

#### setup_git
cat > .gitconfig <<\EOF
[user]
    name = Tester Testerov
    email = tester@example.com
EOF
# repos
mkdir repo && git -C repo init --bare
ORIGIN=$PWD/repo
git clone "file://$ORIGIN" a
git clone "file://$ORIGIN" b
git clone "file://$ORIGIN" c

echo "===### setup_gpg ==="
gpg -K 2>/dev/null
( echo "keyid-format long"; echo "no-permission-warning" ) > .gnupg/gpg.conf

echo "===### initialize_gpg_keys ==="
gpg --import "$SCRIPT_DIR"/fixtures/gpg_keys.gpg
GNUPGHOME="$ORIGIN" gpg --import "$SCRIPT_DIR"/fixtures/unknown_gpg_keys.gpg
GNUPGHOME="$ORIGIN" gpg_fix_trust
export KEYA=`get_key TesterA`
export KEYB=`get_key TesterB`
export KEYC=`get_key TesterC`
export KEYD=`get_key TesterD`
export KEYE=`get_key Expired`

echo a >> a/a.txt && git -C a add a.txt && git -C a commit -m 't1' -S$KEYA
echo a >> a/a.txt && git -C a add a.txt && git -C a commit -m 't2' -S$KEYA
echo a >> a/a.txt && git -C a add a.txt && git -C a commit -m 't3' -S$KEYA

git -C a push origin master
git -C b pull origin master
git -C c pull origin master

echo "=== nothing is signed with a trusted key => show commits ==="
git trustcheck -C a -s | wc -l | assert 1
git trustcheck HEAD -C a -s | wc -l | assert 3

echo "=== trusted and no file ==="
gpg_fix_trust
git trustcheck -C a -s | wc -l | assert 0
git trustcheck HEAD -C a -s | wc -l | assert 0

echo "=== trusted and other keys ==="
git trustcheck -C a -a $KEYB
git trustcheck -C a -s | wc -l | assert 1
git trustcheck HEAD -C a -s | wc -l | assert 3

echo "=== trusted and ok key ==="
git trustcheck -C a -a $KEYA
git trustcheck -C a -s | wc -l | assert 0
git trustcheck HEAD -C a -s | wc -l | assert 0

echo "=== check with local dir ==="
echo "= first no modifications"
git trustcheck HEAD -C c -s | wc -l | assert 0
echo "= then create local gpg dir"
git -C c trustcheck --setup-gpg-home
git trustcheck HEAD -C c -s | wc -l | assert 3
git gpg -k | wc -l | grep -q 0 || exit 1
echo "= then unset local gpg dir"
git trustcheck --unset-gpg-home -C c
git trustcheck HEAD -C c -s | wc -l | assert 0
echo "= setup and fill"
git trustcheck --setup-gpg-home -C c
gpg --export-secret-keys $KEYA | git -C c gpg --import
gpg --export-ownertrust | grep $KEYA | git -C c gpg --import-ownertrust
git trustcheck HEAD -C c -s | wc -l | assert 0
git trustcheck HEAD -C c

echo "=== unsigned children ==="
echo a >> a/a.txt && git -C a add a.txt && git -C a commit -m 't4'
echo a >> a/a.txt && git -C a add a.txt && git -C a commit -m 't5'
echo a >> a/a.txt && git -C a add a.txt && git -C a commit -m 't6' -S$KEYA
git trustcheck HEAD -C a -s | wc -l | assert 0
git trustcheck HEAD -C a -s -c | wc -l | assert 2

echo "=== merge ==="
git -C b pull
echo b >> b/b.txt && git -C b add b.txt && git -C b commit -m 'b1' -S$KEYB
git -C a push
git -C b pull --no-edit
echo "= the merge is not signed"
git trustcheck HEAD -C b -s | wc -l | assert 1
echo "= when merge is signed"
git -C b commit --amend -m 'tmp' -S$KEYB
git trustcheck HEAD -C b -s | wc -l | assert 0

echo "=== revoked ==="
echo b >> b/b.txt && git -C b add b.txt && git -C b commit -m 'b1' -S$KEYD
git trustcheck HEAD -C b -s | wc -l | assert 0
(echo y; echo 2; echo; echo y;) | gpg --no-tty --command-fd 0 -a --gen-revoke $KEYD | gpg --import
git trustcheck HEAD -C b -s | wc -l | assert 1


echo "ALL DONE - TESTS PASSED :)"
