import net.runelite.mapping.Export;
import net.runelite.mapping.Implements;
import net.runelite.mapping.ObfuscatedName;
import net.runelite.mapping.ObfuscatedSignature;

@ObfuscatedName("cd")
@Implements("AttackOption")
public enum AttackOption {
   @ObfuscatedName("r")
   @ObfuscatedSignature(signature = "Lcd;")
   @Export("AttackOption_hidden")
   AttackOption_hidden(3),
   @ObfuscatedName("a")
   @ObfuscatedSignature(signature = "Lcd;")
   @Export("AttackOption_alwaysRightClick")
   AttackOption_alwaysRightClick(4);
}
