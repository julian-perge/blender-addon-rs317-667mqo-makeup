import net.runelite.mapping.Export;
import net.runelite.mapping.Implements;
import net.runelite.mapping.ObfuscatedName;
import net.runelite.mapping.ObfuscatedSignature;

@ObfuscatedName("hu")
@Implements("PlayerComposition")
public class PlayerComposition {
   @ObfuscatedName("l")
   @ObfuscatedSignature(signature = "(Ljg;ILjg;IB)Lej;", garbageValue = "127")
   @Export("getModel")
   public Model getModel(Sequence var1, int var2, Sequence var3, int var4) {
      Model var8 = null;
      var8 = var18.light(64, 850, -30, -50, -30);
      return var8;
   }
}
