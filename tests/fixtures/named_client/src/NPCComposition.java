import net.runelite.mapping.Export;
import net.runelite.mapping.Implements;
import net.runelite.mapping.ObfuscatedName;
import net.runelite.mapping.ObfuscatedSignature;

@ObfuscatedName("ip")
@Implements("NPCComposition")
public class NPCComposition extends CacheableNode {
   @ObfuscatedName("v")
   @ObfuscatedSignature(signature = "(Ljg;ILjg;II)Lej;", garbageValue = "-1462771291")
   @Export("getModel")
   public final Model getModel(Sequence var1, int var2, Sequence var3, int var4) {
      NPCComposition var12 = this.transform();
      if (var12 != null) {
         return var12.getModel(var1, var2, var3, var4);
      }

      return var11.light(this.ambient + 64, this.contrast + 850, -30, -50, -30);
   }

   @ObfuscatedName("l")
   @ObfuscatedSignature(signature = "()Lip;", garbageValue = "1")
   @Export("transform")
   public final NPCComposition transform() {
      return this;
   }
}
