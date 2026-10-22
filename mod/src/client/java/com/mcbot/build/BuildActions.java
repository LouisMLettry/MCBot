package com.mcbot.build;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mcbot.BotException;
import com.mcbot.Names;
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
 * Building actions: game mode, flying, choosing the block in hand, placing and breaking blocks.
 * All these methods run on the game thread.
 */
public final class BuildActions {
	/** Index of the first hotbar slot in the player's inventory menu. */
	private static final int HOTBAR_MENU_OFFSET = 36;

	private BuildActions() {
	}

	// --- Game mode --------------------------------------------------------------------------------

	public static GameType parseGameMode(String name) {
		GameType mode = GameType.byName(name, null);
		if (mode == null) {
			throw new BotException("Unknown game mode: '" + name + "' (survival, creative, adventure, spectator)");
		}
		return mode;
	}

	/** Asks the integrated server (singleplayer world) to change the player's game mode; does not need cheats. */
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

	/** True once the client has received the new game mode (and, in creative, the right to fly). */
	public static boolean isGameModeApplied(Minecraft client, GameType mode) {
		LocalPlayer player = client.player;
		if (player == null || client.gameMode == null || client.gameMode.getPlayerMode() != mode) {
			return false;
		}
		return !mode.isCreative() || player.getAbilities().mayfly;
	}

	// --- Flying -----------------------------------------------------------------------------------

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
			// On the ground, the game turns flying off at the next tick: take off by about one block.
			Vec3 motion = player.getDeltaMovement();
			player.setDeltaMovement(motion.x, 0.5, motion.z);
		}
	}

	// --- Choosing the block -----------------------------------------------------------------------

	/**
	 * Puts {@code itemId} in hand. In creative, the item is created in slot {@code slot} (0-8, -1 = current
	 * slot); otherwise, it must already be in the hotbar.
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
		result.addProperty("item", Names.of(id));
		result.addProperty("is_block", item instanceof BlockItem);
		return result;
	}

	// --- Placing and breaking ---------------------------------------------------------------------

	/**
	 * Places the block held in hand at position {@code pos} (which must be empty or replaceable, like grass).
	 * The target cell itself is "clicked": no neighbouring block is needed, so blocks can be placed in mid-air.
	 * {@code face} is the clicked face; it orients some blocks (logs, slabs, stairs).
	 *
	 * <p>If the cell already holds the held block, nothing is done ({@code already_there}). If it holds another
	 * block, that block is broken first when {@code replace} is true (creative only); otherwise the placement fails
	 * ({@code occupied}).
	 */
	public static JsonObject placeBlock(Minecraft client, BlockPos pos, Direction face, boolean look, boolean replace) {
		LocalPlayer player = requirePlayer(client);
		ClientLevel level = client.level;
		JsonObject result = targetResult(pos, "placed");

		if (!(player.getMainHandItem().getItem() instanceof BlockItem held)) {
			return failure(result, "no_block_selected", "No block in hand: call select_block first");
		}
		BlockState existing = level.getBlockState(pos);
		boolean occupied = !existing.canBeReplaced();
		if (occupied && existing.is(held.getBlock())) {
			result.addProperty("block", blockId(existing));
			return failure(result, "already_there", "This block is already here");
		}
		if (occupied && !replace) {
			result.addProperty("block", blockId(existing));
			return failure(result, "occupied", "Position already occupied by " + blockId(existing));
		}
		if (occupied && !client.gameMode.getPlayerMode().isCreative()) {
			throw new BotException("Replacing blocks is only supported in build mode (creative)");
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
			// The server orients some blocks (doors, stairs, torches…) from where the player looks: send it the
			// new rotation right away, otherwise it would use the one from the previous tick.
			player.connection.send(new ServerboundMovePlayerPacket.Rot(player.getYRot(), player.getXRot(), player.onGround()));
		}
		if (occupied) {
			// Replacing: break the old block first. The server receives the break and the placement in this order.
			client.gameMode.startDestroyBlock(pos, Direction.UP);
			if (!level.getBlockState(pos).canBeReplaced()) {
				result.addProperty("block", blockId(existing));
				return failure(result, "rejected", "The game refused to break " + blockId(existing));
			}
			result.addProperty("replaced", blockId(existing));
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

	/** Instantly breaks the block at {@code pos} (build mode / creative only). */
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

	// --- Utilities --------------------------------------------------------------------------------

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
		return Names.of(BuiltInRegistries.ITEM.getKey(stack.getItem()));
	}

	private static String blockId(BlockState state) {
		return Names.of(BuiltInRegistries.BLOCK.getKey(state.getBlock()));
	}

	private static JsonObject checkReach(LocalPlayer player, BlockPos pos, JsonObject result) {
		if (player.canInteractWithBlock(pos, 0.0)) {
			return null;
		}
		double distance = Math.sqrt(new AABB(pos).distanceToSqr(player.getEyePosition()));
		return failure(result, "out_of_reach",
				String.format("Too far: %.1f blocks (max %.1f)", distance, player.blockInteractionRange()));
	}

	/** Result initialised as "failed" ({@code successKey} = false), then completed by the action. */
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
