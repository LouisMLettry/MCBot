package com.mcbot;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mcbot.build.BuildActions;
import com.mcbot.capture.FrameCapture;
import com.mcbot.net.BotResponse;
import com.mcbot.world.BlockScan;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Options;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.player.Abilities;
import net.minecraft.world.level.GameType;
import net.minecraft.world.phys.Vec3;

import java.util.Map;
import java.util.Queue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.function.BooleanSupplier;

/**
 * Exécute les commandes reçues sur le thread du jeu, un tick client à la fois.
 *
 * <p>Une commande {@code step} maintient les touches demandées pendant {@code ticks} ticks (20 ticks = 1 s),
 * en répartissant la rotation de la caméra sur ces ticks, puis répond avec l'état du joueur et, si demandé,
 * une image. Les touches restent enfoncées jusqu'à la commande suivante, ce qui évite les à-coups entre deux pas ;
 * elles sont toutes relâchées à la déconnexion du client.
 *
 * <p>Les commandes de construction ({@code game_mode}, {@code fly}, {@code select_block}, {@code place_block},
 * {@code break_block}) sont exécutées immédiatement ; {@code game_mode} répond une fois le changement reçu par le client.
 *
 * <p>La commande {@code blocks} renvoie les blocs d'une boîte du monde (voir {@link BlockScan}), lus au même tick
 * que l'état du joueur.
 */
public class BotController {
	private static final int MAX_TICKS_PER_STEP = 20 * 60;
	private static final int GAME_MODE_TIMEOUT_TICKS = 100;
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
	/** Rallume le vol s'il a été coupé (double appui sur saut, atterrissage puis saut…). */
	private boolean keepFlying;

	// Commande en cours (step, ou attente d'un changement de mode de jeu)
	private BotRequest current;
	private int ticksLeft;
	private float yawPerTick;
	private float pitchPerTick;
	private boolean captureFrame;
	private BooleanSupplier waitCondition;

	/** Appelé depuis le thread réseau : la commande sera traitée au prochain tick du jeu. */
	public CompletableFuture<BotResponse> submit(JsonObject json) {
		CompletableFuture<BotResponse> future = new CompletableFuture<>();
		queue.add(new BotRequest(json, future));
		return future;
	}

	/** Appelé depuis le thread réseau à la déconnexion : relâche les touches au prochain tick. */
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
				finish(buildResponse(client, null));
			} else if (--ticksLeft <= 0) {
				finish(BotResponse.error("Timed out waiting for the game mode change"));
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
					JsonObject result = BuildActions.placeBlock(client, getBlockPos(json), face, getBoolean(json, "look", true));
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
		current = request;
		ticksLeft = GAME_MODE_TIMEOUT_TICKS;
		waitCondition = () -> BuildActions.isGameModeApplied(client, mode);
	}

	/**
	 * Boîte demandée par une requête {@code blocks} : un chunk entier ({@code chunk} = [cx, cz]), un cube de rayon
	 * {@code radius} centré sur le bloc des pieds du joueur, ou deux coins {@code min} et {@code max}.
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

	/** Le programme Python a le focus : on empêche le jeu de se mettre en pause et on ferme le menu Pause. */
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
		// Pas de queue.clear() : la file peut déjà contenir la première requête du client suivant.
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

	/** Coordonnées données sous forme de tableau [x, y, z]. */
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
