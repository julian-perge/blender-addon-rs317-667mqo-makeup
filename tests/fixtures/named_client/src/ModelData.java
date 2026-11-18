import net.runelite.mapping.Export;
import net.runelite.mapping.Implements;
import net.runelite.mapping.ObfuscatedName;
import net.runelite.mapping.ObfuscatedSignature;

@ObfuscatedName("dv")
@Implements("ModelData")
public class ModelData extends Renderable {
   @ObfuscatedName("ae")
   @Export("vertexSkins")
   int[] vertexSkins;
   @ObfuscatedName("ac")
   byte[] field1793;

   @ObfuscatedName("ae")
   @ObfuscatedSignature(signature = "(IIIII)Lej;")
   @Export("light")
   public final Model light(int var1, int var2, int var3, int var4, int var5) {
      Model var8 = new Model();
      var8.boundsType = this.vertexSkins.length;
      byte[] var9 = this.field1793;
      return var8;
   }
}
