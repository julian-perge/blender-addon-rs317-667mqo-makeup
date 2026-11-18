import net.runelite.mapping.Export;
import net.runelite.mapping.Implements;
import net.runelite.mapping.ObfuscatedName;
import net.runelite.mapping.ObfuscatedSignature;

@ObfuscatedName("ej")
@Implements("Model")
public class Model extends Renderable {
   @ObfuscatedName("as")
   @Export("modelViewportYs")
   static int[] modelViewportYs = new int[4700];
   @ObfuscatedName("ae")
   @Export("boundsType")
   int boundsType;
}
