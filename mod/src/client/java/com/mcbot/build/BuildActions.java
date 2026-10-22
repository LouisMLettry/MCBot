package com.mcbot.build;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mcbot.BotException;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.commands.arguments.EntityAnchorArgument;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.protocol.game.ServerboundMovePlayerPacket;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Abilities;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;

import java.util.UUID;

/**
 * Actions de construction : mode de jeu, vol, choix du bloc en main, pose et destruction de blocs.
 * Toutes ces méthodes s'exécutent sur le thread du jeu.
 */
public final class BuildActions {
	/** Index du premier emplacement de la barre d'accès rapide dans le menu d'inventaire du joueur. */
	private static final int HOTBAR_MENU_OFFSET = 36;

	private BuildActions() {
	}

	// --- Mode de jeu ------------------------------------------------------------------------------

	public static GameType parseGameMode(String name) {
		GameType mode = GameType.byName(name, null);
		if (mode == null) {
			throw new BotException("Unknown game mode: '" + name + "' (survival, creative, adventure, spectator)");
		}
		return mode;
	}

	/** Demande au serveur intégré (monde solo) de changer le mode de jeu du joueur ; ne nécessite pas les cheats. */
	public static void requestGameMode(Minecraft client, GameType mode) {
		IntegratedServer server = client.getSingleplayerServer();
		if (server == null) {
			throw new BotException("Changing the game mode requires a singleplayer world");
		}
		UUID playerId = requirePlayer(client).getUUID();
		server.execute(() -> {
			ServerPlayer serverPlayer = server.getPlayerList().getPlayer(playerId);
			if (serverPlayer != null) {
				serverPlayer.setGameMode(mode);
			}
		});
	}

	/** Vrai quand le client a reçu le nouveau mode de jeu (et, en créatif, le droit de voler). */
	public static boolean isGameModeApplied(Minecraft client, GameType mode) {
		LocalPlayer player = client.player;
		if (player == null || client.gameMode == null || client.gameMode.getPlayerMode() != mode) {
			return false;
		}
		return !mode.isCreative() || player.getAbilities().mayfly;
	}

	// --- Vol --------------------------------------------------------------------------------------

	public static void setFlying(LocalPlayer player, boolean enabled) {
		Abilities abilities = player.getAbilities();
		if (enabled && !abilities.mayfly) {
			throw new BotException("Flying is not allowed in this game mode: enable build mode (creative) first");
		}
		if (abilities.flying != enabled) {
			abilities.flying = enabled;
			player.onUpdateAbilities();
		}
		if (enabled && player.onGround()) {
			// Au sol, le jeu coupe le vol au tick suivant : on décolle d'environ un bloc.
			Vec3 motion = player.getDeltaMovement();
			player.setDeltaMovement(motion.x, 0.5, motion.z);
		}
	}

	// --- Choix du bloc ----------------------------------------------------------------------------

	/**
	 * Met {@code itemId} en main. En créatif, l'objet est créé dans l'emplacement {@code slot} (0-8, -1 = emplacement
	 * actuel) ; sinon, il doit déjà se trouver dans la barre d'accès rapide.
	 */
	public static JsonObject selectItem(Minecraft client, String itemId, int slot) {
		LocalPlayer player = requirePlayer(client);
		ResourceLocation id = ResourceLocation.tryParse(itemId);
		if (id == null || !BuiltInRegistries.ITEM.containsKey(id)) {
			throw new BotException("Unknown block or item: '" + itemId + "'");
		}
		Item item = BuiltInRegistries.ITEM.get(id);
		Inventory inventory = player.getInventory();
		int hotbarSize = Inventory.getSelectionSize();

		if (client.gameMode.hasInfiniteItems()) {
			if (slot < 0) {
				slot = inventory.selected;
			}
			if (slot >= hotbarSize) {
				throw new BotException("Invalid hotbar slot: " + slot + " (0-" + (hotbarSize - 1) + ")");
			}
			ItemStack stack = new ItemStack(item, item.getDefaultMaxStackSize());
			inventory.setItem(slot, stack);
			client.gameMode.handleCreativeModeItemAdd(stack, HOTBAR_MENU_OFFSET + slot);
		} else {
			slot = -1;
			for (int i = 0; i < hotbarSize && slot < 0; i++) {
				if (inventory.getItem(i).is(item)) {
					slot = i;
				}
			}
			if (slot < 0) {
				throw new BotException("'" + id + "' is not in the hotbar: enable build mode (creative) to use any block");
			}
		}
		inventory.selected = slot;

		JsonObject result = new JsonObject();
		result.addProperty("slot", slot);
		result.addProperty("item", id.toString());
		result.addProperty("is_block", item instanceof BlockItem);
		return result;
	}

	// --- Pose et destruction ----------------------------------------------------------------------

	/**
	 * Pose le bloc tenu en main à la position {@code pos} (qui doit être vide ou remplaçable, comme de l'herbe).
	 * On « clique » directement sur la case visée : pas besoin d'un bloc voisin, on peut donc construire en l'air.
	 * {@code face} est la face cliquée ; elle oriente certains blocs (bûches, dalles, escaliers).
	 */
	public static JsonObject placeBlock(Minecraft client, BlockPos pos, Direction face, boolean look) {
		LocalPlayer player = requirePlayer(client);
		ClientLevel level = client.level;
		JsonObject result = targetResult(pos, "placed");

		BlockState existing = level.getBlockState(pos);
		if (!existing.canBeReplaced()) {
			return failure(result, "occupied", "Position already occupied by " + blockId(existing));
		}
		if (!(player.getMainHandItem().getItem() instanceof BlockItem)) {
			return failure(result, "no_block_selected", "No block in hand: call select_block first");
		}
		JsonObject reachFailure = checkReach(player, pos, result);
		if (reachFailure != null) {
			return reachFailure;
		}
		if (player.getBoundingBox().intersects(new AABB(pos))) {
			return failure(result, "player_in_the_way", "The player is standing in this block");
		}

		Vec3 hitLocation = Vec3.atCenterOf(pos);
		if (look) {
			player.lookAt(EntityAnchorArgument.Anchor.EYES, hitLocation);
			// Le serveur oriente certains blocs (portes, escaliers, torches…) selon le regard du joueur : on lui envoie
			// la nouvelle orientation tout de suite, sinon il utiliserait celle du tick précédent.
			player.connection.send(new ServerboundMovePlayerPacket.Rot(player.getYRot(), player.getXRot(), player.onGround()));
		}
		InteractionResult interaction = client.gameMode.useItemOn(player, InteractionHand.MAIN_HAND,
				new BlockHitResult(hitLocation, face, pos, false));
		if (interaction.shouldSwing()) {
			player.swing(InteractionHand.MAIN_HAND);
		}

		BlockState placed = level.getBlockState(pos);
		boolean success = !placed.canBeReplaced();
		result.addProperty("placed", success);
		result.addProperty("block", blockId(placed));
		result.addProperty("result", interaction.name());
		if (!success) {
			failure(result, "rejected", "The game refused the placement (missing support, entity in the way…)");
		}
		return result;
	}

	/** Casse instantanément le bloc à {@code pos} (mode construction / créatif uniquement). */
	public static JsonObject breakBlock(Minecraft client, BlockPos pos, boolean look) {
		LocalPlayer player = requirePlayer(client);
		if (!client.gameMode.getPlayerMode().isCreative()) {
			throw new BotException("Breaking blocks is only supported in build mode (creative)");
		}
		ClientLevel level = client.level;
		JsonObject result = targetResult(pos, "broken");

		BlockState existing = level.getBlockState(pos);
		if (existing.isAir()) {
			return failure(result, "empty", "There is no block here");
		}
		JsonObject reachFailure = checkReach(player, pos, result);
		if (reachFailure != null) {
			return reachFailure;
		}

		if (look) {
			player.lookAt(EntityAnchorArgument.Anchor.EYES, Vec3.atCenterOf(pos));
		}
		client.gameMode.startDestroyBlock(pos, Direction.UP);
		player.swing(InteractionHand.MAIN_HAND);

		boolean broken = level.getBlockState(pos).isAir();
		result.addProperty("broken", broken);
		result.addProperty("block", blockId(existing));
		if (!broken) {
			failure(result, "rejected", "The game refused to break this block");
		}
		return result;
	}

	// --- Utilitaires ------------------------------------------------------------------------------

	public static LocalPlayer requirePlayer(Minecraft client) {
		if (client.player == null || client.level == null || client.gameMode == null) {
			throw new BotException("No world loaded: join a singleplayer world first");
		}
		return client.player;
	}

	public static Direction parseFace(String name) {
		Direction face = Direction.byName(name);
		if (face == null) {
			throw new BotException("Unknown face: '" + name + "' (up, down, north, south, east, west)");
		}
		return face;
	}

	public static String itemId(ItemStack stack) {
		return BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
	}

	private static String blockId(BlockState state) {
		return BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
	}

	private static JsonObject checkReach(LocalPlayer player, BlockPos pos, JsonObject result) {
		if (player.canInteractWithBlock(pos, 0.0)) {
			return null;
		}
		double distance = Math.sqrt(new AABB(pos).distanceToSqr(player.getEyePosition()));
		return failure(result, "out_of_reach",
				String.format("Too far: %.1f blocks (max %.1f)", distance, player.blockInteractionRange()));
	}

	/** Résultat initialisé à « échec » ({@code successKey} = false), complété ensuite par l'action. */
	private static JsonObject targetResult(BlockPos pos, String successKey) {
		JsonObject result = new JsonObject();
		result.addProperty(successKey, false);
		JsonArray target = new JsonArray();
		target.add(pos.getX());
		target.add(pos.getY());
		target.add(pos.getZ());
		result.add("target", target);
		return result;
	}

	private static JsonObject failure(JsonObject result, String reason, String message) {
		result.addProperty("reason", reason);
		result.addProperty("message", message);
		return result;
	}
}
