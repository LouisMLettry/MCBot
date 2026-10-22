package com.mcbot;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mcbot.build.BuildActions;
import com.mcbot.capture.FrameCapture;
import com.mcbot.net.BotResponse;
import com.mcbot.world.BlockScan;
import com.mcbot.world.BlockWriter;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Options;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.player.Abilities;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.Vec3;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Queue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.function.BooleanSupplier;
import java.util.function.Supplier;

/**
 * Runs the received commands on the game thread, one client tick at a time.
 *
 * <p>A {@code step} command holds the requested keys for {@code ticks} ticks (20 ticks = 1 s),
 * spreading the camera rotation over those ticks, then answers with the player's state and, if requested,
 * an image. Keys stay pressed until the next command, which avoids jerks between two steps;
 * they are all released when the client disconnects.
 *
 * <p>Building commands ({@code game_mode}, {@code fly}, {@code select_block}, {@code place_block},
 * {@code break_block}) run immediately; {@code game_mode} answers once the client has received the change.
 * {@code set_blocks} writes exact block states through the singleplayer server and answers once the client shows
 * them.
 *
 * <p>The {@code blocks} command returns the blocks of a box of the world (see {@link BlockScan}), read at the same tick
 * as the player's state.
 */
public class BotController {
	private static final int MAX_TICKS_PER_STEP = 20 * 60;
	/** Maximum wait for a change to be applied (game mode, written blocks): 5 s. */
	private static final int WAIT_TIMEOUT_TICKS = 100;
	private static final int MIN_FRAME_SIZE = 16;
	private static final int MAX_FRAME_SIZE = 1024;

	private record BotRequest(JsonObject json, CompletableFuture<BotResponse> future) {
	}

	private record Action(boolean forward, boolean back, boolean left, boolean right, boolean jump,
						  boolean sprint, boolean sneak, boolean attack, boolean use, float yaw, float pitch) {
		static final Action NONE = new Action(false, false, false, false, false, false, false, false, false, 0, 0);

		static Action fromJson(JsonObject json) {
			if (json == null) {
				return NONE;
			}
			return new Action(
					getBoolean(json, "forward", false), getBoolean(json, "back", false),
					getBoolean(json, "left", false), getBoolean(json, "right", false),
					getBoolean(json, "jump", false), getBoolean(json, "sprint", false),
					getBoolean(json, "sneak", false), getBoolean(json, "attack", false),
					getBoolean(json, "use", false),
					getFloat(json, "yaw", 0), getFloat(json, "pitch", 0));
		}
	}

	private final Queue<BotRequest> queue = new ConcurrentLinkedQueue<>();
	private volatile boolean releaseRequested;

	private int frameWidth = 128;
	private int frameHeight = 128;
	private long tickCount;
	private Boolean savedPauseOnLostFocus;
	private boolean keysHeld;
	/** Turns flying back on if it was turned off (double jump press, landing then jumping…). */
	private boolean keepFlying;

	// Current command (step, or waiting for a change to be applied: game mode, written blocks)
	private BotRequest current;
	private int ticksLeft;
	private float yawPerTick;
	private float pitchPerTick;
	private boolean captureFrame;
	private BooleanSupplier waitCondition;
	private Supplier<BotResponse> waitResponse;
	private String waitTimeoutMessage;

	/** Called from the network thread: the command will be handled at the next game tick. */
	public CompletableFuture<BotResponse> submit(JsonObject json) {
		CompletableFuture<BotResponse> future = new CompletableFuture<>();
		queue.add(new BotRequest(json, future));
		return future;
	}

	/** Called from the network thread on disconnect: releases the keys at the next tick. */
	public void releaseAll() {
		releaseRequested = true;
	}

	public void onEndTick(Minecraft client) {
		tickCount++;

		if (releaseRequested) {
			releaseRequested = false;
			release(client);
		}
		maintainFlight(client.player);

		if (current == null) {
			BotRequest next = queue.poll();
			if (next != null) {
				begin(client, next);
			}
			return;
		}

		if (waitCondition != null) {
			if (waitCondition.getAsBoolean()) {
				finish(waitResponse.get());
			} else if (--ticksLeft <= 0) {
				finish(BotResponse.error(waitTimeoutMessage));
			}
			return;
		}

		LocalPlayer player = client.player;
		if (player == null) {
			finish(BotResponse.error("No world loaded: join a singleplayer world first"));
			return;
		}

		player.setYRot(player.getYRot() + yawPerTick);
		player.setXRot(Mth.clamp(player.getXRot() + pitchPerTick, -90f, 90f));
		ticksLeft--;
		if (ticksLeft <= 0) {
			finish(buildResponse(client, null));
		}
	}

	private void begin(Minecraft client, BotRequest request) {
		JsonObject json = request.json();
		String type = json.has("type") ? json.get("type").getAsString() : "";

		try {
			switch (type) {
				case "ping" -> request.future().complete(buildResponse(client, null));
				case "config" -> {
					frameWidth = Mth.clamp(getInt(json, "width", frameWidth), MIN_FRAME_SIZE, MAX_FRAME_SIZE);
					frameHeight = Mth.clamp(getInt(json, "height", frameHeight), MIN_FRAME_SIZE, MAX_FRAME_SIZE);
					if (json.has("hide_gui")) {
						client.options.hideGui = json.get("hide_gui").getAsBoolean();
					}
					request.future().complete(buildResponse(client, null));
				}
				case "step" -> beginStep(client, request);
				case "game_mode" -> beginGameMode(client, request);
				case "set_blocks" -> beginSetBlocks(client, request);
				case "fly" -> {
					LocalPlayer player = BuildActions.requirePlayer(client);
					prepareForControl(client);
					boolean enabled = getBoolean(json, "enabled", true);
					BuildActions.setFlying(player, enabled);
					keepFlying = enabled;
					request.future().complete(buildResponse(client, null));
				}
				case "select_block" -> {
					BuildActions.requirePlayer(client);
					JsonObject result = BuildActions.selectItem(client, getString(json, "block"), getInt(json, "slot", -1));
					request.future().complete(buildResponse(client, result));
				}
				case "place_block" -> {
					BuildActions.requirePlayer(client);
					prepareForControl(client);
					Direction face = BuildActions.parseFace(json.has("face") ? getString(json, "face") : "up");
					JsonObject result = BuildActions.placeBlock(client, getBlockPos(json), face, getBoolean(json, "look", true),
							getBoolean(json, "replace", false));
					request.future().complete(buildResponse(client, result));
				}
				case "break_block" -> {
					BuildActions.requirePlayer(client);
					prepareForControl(client);
					JsonObject result = BuildActions.breakBlock(client, getBlockPos(json), getBoolean(json, "look", true));
					request.future().complete(buildResponse(client, result));
				}
				case "blocks" -> {
					BlockScan.Result scan = scanBlocks(client, json);
					request.future().complete(new BotResponse(buildResponse(client, scan.info()).info(), scan.data()));
				}
				default -> request.future().complete(BotResponse.error("Unknown request type: '" + type + "'"));
			}
		} catch (BotException e) {
			request.future().complete(BotResponse.error(e.getMessage()));
		} catch (RuntimeException e) {
			request.future().complete(BotResponse.error(e.toString()));
		}
	}

	private void beginStep(Minecraft client, BotRequest request) {
		LocalPlayer player = BuildActions.requirePlayer(client);
		prepareForControl(client);

		JsonObject json = request.json();
		Action action = Action.fromJson(json.has("action") ? json.getAsJsonObject("action") : null);
		int ticks = Mth.clamp(getInt(json, "ticks", 1), 0, MAX_TICKS_PER_STEP);

		applyKeys(client.options, action);
		captureFrame = getBoolean(json, "frame", false);
		current = request;

		if (ticks == 0) {
			player.setYRot(player.getYRot() + action.yaw());
			player.setXRot(Mth.clamp(player.getXRot() + action.pitch(), -90f, 90f));
			finish(buildResponse(client, null));
			return;
		}

		ticksLeft = ticks;
		yawPerTick = action.yaw() / ticks;
		pitchPerTick = action.pitch() / ticks;
	}

	private void beginGameMode(Minecraft client, BotRequest request) {
		BuildActions.requirePlayer(client);
		GameType mode = BuildActions.parseGameMode(getString(request.json(), "mode"));
		prepareForControl(client);
		if (!mode.isCreative()) {
			keepFlying = false;
		}
		if (BuildActions.isGameModeApplied(client, mode)) {
			request.future().complete(buildResponse(client, null));
			return;
		}

		BuildActions.requestGameMode(client, mode);
		waitFor(request, () -> BuildActions.isGameModeApplied(client, mode), () -> buildResponse(client, null),
				"Timed out waiting for the game mode change");
	}

	/**
	 * Writes exact block states: {@code blocks} = [[x, y, z, "oak_stairs[facing=east]"], …]. Every state is parsed
	 * before anything is written; the response comes once the client shows the new blocks.
	 */
	private void beginSetBlocks(Minecraft client, BotRequest request) {
		BuildActions.requirePlayer(client);
		JsonElement element = request.json().get("blocks");
		if (element == null || !element.isJsonArray()) {
			throw new BotException("Missing or invalid parameter: 'blocks' (expected [[x, y, z, \"block\"], ...])");
		}
		List<BlockPos> positions = new ArrayList<>();
		List<BlockState> states = new ArrayList<>();
		for (JsonElement entry : element.getAsJsonArray()) {
			JsonArray values = entry.getAsJsonArray();
			if (values.size() != 4) {
				throw new BotException("Invalid block entry: " + entry + " (expected [x, y, z, \"block\"])");
			}
			positions.add(new BlockPos(values.get(0).getAsInt(), values.get(1).getAsInt(), values.get(2).getAsInt()));
			states.add(BlockWriter.parse(values.get(3).getAsString()));
		}
		prepareForControl(client);

		CompletableFuture<Void> written = BlockWriter.write(client, positions, states);
		waitFor(request,
				() -> written.isDone() && (written.isCompletedExceptionally() || BlockWriter.isVisible(client.level, positions, states)),
				() -> {
					if (written.isCompletedExceptionally()) {
						return BotResponse.error("The server failed to write the blocks: " + written.exceptionNow());
					}
					JsonObject result = new JsonObject();
					result.add("blocks", BlockWriter.names(states));
					return buildResponse(client, result);
				},
				"Timed out waiting for the blocks to be written");
	}

	/** Answers {@code request} with {@code response} once {@code condition} holds, checked at every tick. */
	private void waitFor(BotRequest request, BooleanSupplier condition, Supplier<BotResponse> response, String timeoutMessage) {
		current = request;
		ticksLeft = WAIT_TIMEOUT_TICKS;
		waitCondition = condition;
		waitResponse = response;
		waitTimeoutMessage = timeoutMessage;
	}

	/**
	 * Box requested by a {@code blocks} request: a whole chunk ({@code chunk} = [cx, cz]), a cube of radius
	 * {@code radius} centred on the block of the player's feet, or two corners {@code min} and {@code max}.
	 */
	private static BlockScan.Result scanBlocks(Minecraft client, JsonObject json) {
		LocalPlayer player = BuildActions.requirePlayer(client);
		boolean states = getBoolean(json, "states", false);
		if (json.has("chunk")) {
			JsonArray chunk = json.getAsJsonArray("chunk");
			return BlockScan.scanChunk(client.level, chunk.get(0).getAsInt(), chunk.get(1).getAsInt(), states);
		}
		if (json.has("radius")) {
			int radius = getInt(json, "radius", 0);
			if (radius < 0) {
				throw new BotException("Invalid radius: " + radius);
			}
			BlockPos feet = player.blockPosition();
			return BlockScan.scan(client.level, feet.offset(-radius, -radius, -radius), feet.offset(radius, radius, radius), states);
		}
		return BlockScan.scan(client.level, getBlockPos(json, "min"), getBlockPos(json, "max"), states);
	}

	/** The Python program has the focus: keep the game from pausing and close the Pause menu. */
	private void prepareForControl(Minecraft client) {
		if (savedPauseOnLostFocus == null) {
			savedPauseOnLostFocus = client.options.pauseOnLostFocus;
			client.options.pauseOnLostFocus = false;
		}
		if (client.screen instanceof PauseScreen) {
			client.setScreen(null);
		}
	}

	private void maintainFlight(LocalPlayer player) {
		if (!keepFlying || player == null) {
			return;
		}
		Abilities abilities = player.getAbilities();
		if (abilities.mayfly && !abilities.flying && !player.onGround()) {
			abilities.flying = true;
			player.onUpdateAbilities();
		}
	}

	private void finish(BotResponse response) {
		BotRequest request = current;
		current = null;
		captureFrame = false;
		waitCondition = null;
		waitResponse = null;
		waitTimeoutMessage = null;
		request.future().complete(response);
	}

	private void release(Minecraft client) {
		if (keysHeld) {
			applyKeys(client.options, Action.NONE);
			keysHeld = false;
		}
		keepFlying = false;
		if (savedPauseOnLostFocus != null) {
			client.options.pauseOnLostFocus = savedPauseOnLostFocus;
			savedPauseOnLostFocus = null;
		}
		// No queue.clear(): the queue may already hold the first request of the next client.
		if (current != null) {
			finish(BotResponse.error("Client disconnected"));
		}
	}

	private void applyKeys(Options options, Action action) {
		options.keyUp.setDown(action.forward());
		options.keyDown.setDown(action.back());
		options.keyLeft.setDown(action.left());
		options.keyRight.setDown(action.right());
		options.keyJump.setDown(action.jump());
		options.keySprint.setDown(action.sprint());
		options.keyShift.setDown(action.sneak());
		options.keyAttack.setDown(action.attack());
		options.keyUse.setDown(action.use());
		keysHeld = true;
	}

	private BotResponse buildResponse(Minecraft client, JsonObject extra) {
		JsonObject info = new JsonObject();
		info.addProperty("ok", true);
		info.addProperty("tick", tickCount);
		info.addProperty("paused", client.isPaused());
		info.addProperty("screen", client.screen == null ? null : client.screen.getClass().getSimpleName());
		info.addProperty("frame_width", frameWidth);
		info.addProperty("frame_height", frameHeight);

		LocalPlayer player = client.player;
		info.addProperty("in_world", player != null);
		if (player != null) {
			info.add("pos", vector(player.getX(), player.getY(), player.getZ()));
			Vec3 motion = player.getDeltaMovement();
			info.add("motion", vector(motion.x, motion.y, motion.z));
			info.addProperty("yaw", Mth.wrapDegrees(player.getYRot()));
			info.addProperty("pitch", player.getXRot());
			info.addProperty("on_ground", player.onGround());
			info.addProperty("health", player.getHealth());
			info.addProperty("flying", player.getAbilities().flying);
			info.addProperty("may_fly", player.getAbilities().mayfly);
			info.addProperty("reach", player.blockInteractionRange());
			info.addProperty("selected_slot", player.getInventory().selected);
			info.addProperty("held_item", BuildActions.itemId(player.getMainHandItem()));
			if (client.gameMode != null) {
				info.addProperty("game_mode", client.gameMode.getPlayerMode().getName());
			}
		}
		if (extra != null) {
			for (Map.Entry<String, JsonElement> entry : extra.entrySet()) {
				info.add(entry.getKey(), entry.getValue());
			}
		}

		byte[] frame = captureFrame && player != null ? FrameCapture.capture(client, frameWidth, frameHeight) : null;
		if (frame != null) {
			info.addProperty("payload", "frame");
		}
		return new BotResponse(info, frame);
	}

	private static JsonArray vector(double x, double y, double z) {
		JsonArray array = new JsonArray();
		array.add(x);
		array.add(y);
		array.add(z);
		return array;
	}

	private static BlockPos getBlockPos(JsonObject json) {
		if (!json.has("x") || !json.has("y") || !json.has("z")) {
			throw new BotException("Missing block coordinates: x, y, z");
		}
		return new BlockPos(json.get("x").getAsInt(), json.get("y").getAsInt(), json.get("z").getAsInt());
	}

	/** Coordinates given as an array [x, y, z]. */
	private static BlockPos getBlockPos(JsonObject json, String key) {
		JsonElement element = json.get(key);
		if (element == null || !element.isJsonArray() || element.getAsJsonArray().size() != 3) {
			throw new BotException("Missing or invalid parameter: '" + key + "' (expected [x, y, z])");
		}
		JsonArray array = element.getAsJsonArray();
		return new BlockPos(array.get(0).getAsInt(), array.get(1).getAsInt(), array.get(2).getAsInt());
	}

	private static boolean getBoolean(JsonObject json, String key, boolean fallback) {
		JsonElement element = json.get(key);
		return element == null || element.isJsonNull() ? fallback : element.getAsBoolean();
	}

	private static float getFloat(JsonObject json, String key, float fallback) {
		JsonElement element = json.get(key);
		return element == null || element.isJsonNull() ? fallback : element.getAsFloat();
	}

	private static int getInt(JsonObject json, String key, int fallback) {
		JsonElement element = json.get(key);
		return element == null || element.isJsonNull() ? fallback : element.getAsInt();
	}

	private static String getString(JsonObject json, String key) {
		JsonElement element = json.get(key);
		if (element == null || element.isJsonNull()) {
			throw new BotException("Missing parameter: '" + key + "'");
		}
		return element.getAsString();
	}
}
