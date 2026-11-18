#!/usr/bin/env bash
# Rebuilds a named source tree of the revision 149 client (gamepack-149.jar).
#
#   scripts/named-client/build.sh --gamepack <path to gamepack-149.jar>
#
# Needs JDK 21, Maven, perl and vineflower. Environment variables, each with a default:
#   NAMED_CLIENT_DIR  output folder, default ~/git/osrs-149-named
#   RUNELITE_TREE     read-only RuneLite May 2018 tree, default ~/git/runelite-master
#   RUNELITE_JDK      a JDK 21 home, default: the java on the PATH
#
# Writes to NAMED_CLIENT_DIR: mapped-osrs-149.jar, names-osrs-149.tsv, map-osrs-149.log and src/.
# README.md next to this script says why each patch is needed.

set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd "$here/../.." && pwd)
names_file="$repo/docs/research/client-names.tsv"

out=${NAMED_CLIENT_DIR:-$HOME/git/osrs-149-named}
tree=${RUNELITE_TREE:-$HOME/git/runelite-master}
gamepack=""

while [ $# -gt 0 ]; do
    case $1 in
        --gamepack)
            gamepack=${2:-}
            shift 2
            ;;
        *)
            echo "usage: build.sh --gamepack <path to gamepack-149.jar>" >&2
            exit 2
            ;;
    esac
done
if [ -z "$gamepack" ] || [ ! -f "$gamepack" ]; then
    echo "usage: build.sh --gamepack <path to gamepack-149.jar>" >&2
    exit 2
fi
gamepack=$(cd "$(dirname "$gamepack")" && pwd)/$(basename "$gamepack")

if [ -n "${RUNELITE_JDK:-}" ]; then
    export JAVA_HOME=$RUNELITE_JDK
    java=$RUNELITE_JDK/bin/java
else
    java=$(command -v java || true)
fi
for tool in "$java" mvn perl vineflower; do
    if [ -z "$tool" ] || ! command -v "$tool" >/dev/null 2>&1; then
        echo "missing tool: ${tool:-java}. Install JDK 21, Maven, perl and vineflower (brew install vineflower)." >&2
        exit 1
    fi
done
if ! "$java" -version 2>&1 | head -1 | grep -q '"21\.'; then
    echo "the java in use is not JDK 21. Set RUNELITE_JDK to a JDK 21 home." >&2
    exit 1
fi
if [ ! -d "$tree" ]; then
    echo "missing RuneLite tree: set RUNELITE_TREE to the May 2018 tree." >&2
    exit 1
fi

mkdir -p "$out"
rl=$out/work/runelite
mkdir -p "$out/work"

# The build runs in a copy, so the reference tree stays unpatched. On APFS, cp -c makes a clone.
if [ ! -d "$rl" ]; then
    if ! cp -c -R "$tree" "$rl" 2>/dev/null; then
        cp -R "$tree" "$rl"
    fi

    perl -pi -e 's{http://repo1\.maven\.org/maven2}{https://repo1.maven.org/maven2}g; s{http://repo\.runelite\.net}{https://repo.runelite.net}g' \
        "$rl/pom.xml"
    perl -0pi -e 's{\s*<dependency>\s*<groupId>net\.runelite\.rs</groupId>\s*<artifactId>(client|vanilla)</artifactId>.*?</dependency>}{}gs' \
        "$rl/deobfuscator/pom.xml"
    for f in Client class41 class178; do
        perl -pi -e 's{JSObject\.getWindow\(\w+\)}{((JSObject) null)}g' "$rl/runescape-client/src/main/java/$f.java"
    done
    perl -0pi -e 's{"Errors in annotation checker, exiting"\);\s*System\.exit\(-1\);}{"Errors in annotation checker, continuing");}' \
        "$rl/deobfuscator/src/main/java/net/runelite/deob/updater/UpdateMappings.java"

    failed=""
    if grep -q '<artifactId>vanilla</artifactId>' "$rl/deobfuscator/pom.xml"; then
        failed="deobfuscator/pom.xml still lists the vanilla test dependency"
    elif grep -q 'annotation checker, exiting' "$rl/deobfuscator/src/main/java/net/runelite/deob/updater/UpdateMappings.java"; then
        failed="UpdateMappings still exits on annotation checker errors"
    elif grep -q 'JSObject\.getWindow(' "$rl"/runescape-client/src/main/java/{Client,class41,class178}.java; then
        failed="a JSObject.getWindow call is still in the client"
    fi
    if [ -n "$failed" ]; then
        rm -rf "$rl"
        echo "patch failed: $failed. The RuneLite tree differs from the May 2018 tree that the patches expect." >&2
        exit 1
    fi
fi

(
    cd "$rl"
    mvn -B -q -pl runescape-api,runescape-client,deobfuscator -am package \
        -Dmaven.test.skip=true -Dcheckstyle.skip -Djava.version=1.8 -Dlombok.version=1.18.38
)

cp_jar=$rl/deobfuscator/target/deob-1.3.9-SNAPSHOT-jar-with-dependencies.jar
client_jar=$rl/runescape-client/target/client-1.3.9-SNAPSHOT.jar
deob=$out/work/deob-osrs-149.jar
mapped=$out/mapped-osrs-149.jar
names=$out/names-osrs-149.tsv

echo "deobfuscate"
"$java" -Xmx6g -cp "$cp_jar" net.runelite.deob.Deob "$gamepack" "$deob" >"$out/work/deob-osrs-149.log" 2>&1
echo "map names"
"$java" -Xmx8g -cp "$cp_jar" net.runelite.deob.updater.UpdateMappings "$client_jar" "$deob" "$mapped" >"$out/map-osrs-149.log" 2>&1
"$java" -cp "$cp_jar" "$here/Dump.java" "$mapped" >"$names"

echo "decompile"
# Only the classes of the root package are the client. net/runelite/rs/Opcodes.class is a 126-byte stub that makes
# vineflower stop with an IndexOutOfBoundsException.
rm -rf "$out/src" "$out/work/classes"
mkdir -p "$out/src" "$out/work/classes"
unzip -q "$mapped" '*.class' -x 'net/*' -d "$out/work/classes"
vineflower --silent "$out/work/classes" "$out/src" >"$out/work/vineflower.log" 2>&1

# A name is real when it is not a placeholder of the mapper.
placeholder='^(class|field|method|vmethod)[0-9]+$'
awk -F '\t' -v ph="$placeholder" 'NR > 1 && $5 !~ ph { n[$1]++ } END {
    printf "classes: %d\nfields: %d\nmethods: %d\n", n["class"], n["field"], n["method"] }' "$names"
echo "java files: $(find "$out/src" -name '*.java' | wc -l | tr -d ' ')"

# The seed is written once. After that, sessions edit the file by hand.
if [ ! -f "$names_file" ]; then
    awk -F '\t' -v OFS='\t' -v ph="$placeholder" '
        NR == 1 { print "kind", "obf_class", "obf_member", "descriptor", "name", "evidence"; next }
        $5 !~ ph { print $1, $2, $3, $4, $5, "runelite-mapper" }' "$names" >"$names_file"
    echo "wrote $names_file"
else
    echo "kept $names_file"
fi
