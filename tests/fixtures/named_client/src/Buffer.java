import net.runelite.mapping.Export;
import net.runelite.mapping.Implements;
import net.runelite.mapping.ObfuscatedName;
import net.runelite.mapping.ObfuscatedSignature;

@ObfuscatedName("fe")
@Implements("Buffer")
public class Buffer extends Node {
   @ObfuscatedName("as")
   @ObfuscatedSignature(signature = "([II)V", garbageValue = "2088504046")
   @Export("decryptXtea")
   public void decryptXtea(int[] var1) {
      int var2 = this.offset / 8;
      this.offset = 0;
   }

   @ObfuscatedName("ab")
   @ObfuscatedSignature(signature = "([IIII)V", garbageValue = "65536")
   @Export("decryptXtea")
   public void decryptXtea(int[] var1, int var2, int var3) {
      int var4 = var3 / 8;
      this.offset = var2;
   }
}
