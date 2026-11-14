# A model with no faces stores priority 0

When the add-on writes the footer of a hand-built OSRS-149 model, or of an edit that contradicts its source footer, it computes the priority byte. A priority byte of 255 means that one priority byte follows for every face. Any other value is the one priority of all faces (rule 1 in [osrs-149-codec-client-rules.md](../research/osrs-149-codec-client-rules.md)). A model with no faces has no priority to share, and the client has no case for it, so the inputs do not decide the byte.

The review of PR 6 found that the code and its test called the 0 "our own choice", and that no decision recorded it. On 2026-11-14 the owner settled it: a model with no faces stores 0 as its one shared priority. The client reads it as a shared priority like any value below 255, so the file stays valid. The code and its test do not change.
