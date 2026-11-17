package com.mcbot.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mcbot.BotException;
import com.mcbot.Names;
import net.minecraft.client.Camera;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;

/**
 * Lists the entities (mobs, dropped items, other players…) the client knows about, nearest first, as seen from a
 * {@link View}. Must be called on the game thread.
 *
 * <p>The client only knows the entities the server sends it: those within their tracking range (about 8 chunks for
 * mobs, 6 for dropped items), and never beyond the render distance.
 *
 * <p>With {@code visibility}, each entity also gets:
 * <ul>
 *   <li>{@code line_of_sight}: a ray from the camera reaches the bottom, middle or top of its hitbox without crossing
 *   a block. Blocks count by their visual shape (glass doesn't block, leaves do); fluids are ignored;</li>
 *   <li>{@code in_view}: its hitbox is inside the camera's field of view. The test is conservative: a hitbox just
 *   outside a corner of the image can count as in view.</li>
 * </ul>
 */
public final class EntityScan {
	public static final double DEFAULT_RADIUS = 32;
	public static final double MAX_RADIUS = 256;
	public static final int DEFAULT_LIMIT = 256;
	public static final int MAX_LIMIT = 4096;
	/** Heights of the line of sight targets, as fractions of the hitbox height. */
	private static final double[] SIGHT_HEIGHTS = {0.5, 0.9, 0.1};

	/**
	 * What to list: the entities within {@code radius} of the player's feet or, if {@code box} is given, those whose
	 * hitbox touches it. An empty {@code types} means every type.
	 */
	public record Query(double radius, AABB box, Set<EntityType<?>> types, int limit, boolean visibility) {
	}

	/**
	 * Where the entities are seen from: the camera position, its field of view, and the partial tick used to place
	 * entities between two ticks, as the renderer does.
	 */
	public record View(Vec3 camera, Frustum frustum, float partialTick) {
		/** The camera of a rendered frame, with the frame's view and projection matrices. */
		public static View ofFrame(Camera camera, Matrix4f viewMatrix, Matrix4f projection) {
			return of(camera.getPosition(), viewMatrix, projection, camera.getPartialTickTime());
		}

		/** The player's eyes at the current tick, with the projection of the last rendered frame. */
		public static View ofPlayer(LocalPlayer player, Matrix4f projection) {
			// Same rotation as Camera.setRotation.
			Quaternionf rotation = new Quaternionf().rotationYXZ(Mth.PI - player.getYRot() * Mth.DEG_TO_RAD,
					-player.getXRot() * Mth.DEG_TO_RAD, 0);
			return of(player.getEyePosition(), new Matrix4f().rotation(rotation.conjugate()), projection, 1);
		}

		private static View of(Vec3 camera, Matrix4f viewMatrix, Matrix4f projection, float partialTick) {
			Frustum frustum = new Frustum(viewMatrix, projection);
			frustum.prepare(camera.x, camera.y, camera.z);
			return new View(camera, frustum, partialTick);
		}
	}

	private record Found(Entity entity, Vec3 pos, double distance) {
	}

	private EntityScan() {
	}

	/** Entity type from its name ({@code zombie}; {@code minecraft:zombie} accepted). */
	public static EntityType<?> parseType(String name) {
		ResourceLocation id = ResourceLocation.tryParse(name);
		if (id == null || !BuiltInRegistries.ENTITY_TYPE.containsKey(id)) {
			throw new BotException("Unknown entity type: '" + name + "'");
		}
		return BuiltInRegistries.ENTITY_TYPE.get(id);
	}

	public static JsonArray scan(ClientLevel level, LocalPlayer player, View view, Query query) {
		float partialTick = view.partialTick();
		Vec3 origin = player.getPosition(partialTick);
		AABB area = query.box() != null ? query.box() : new AABB(origin, origin).inflate(query.radius());

		List<Found> found = new ArrayList<>();
		for (Entity entity : level.getEntities(player, area,
				entity -> query.types().isEmpty() || query.types().contains(entity.getType()))) {
			Vec3 pos = entity.getPosition(partialTick);
			double distance = pos.distanceTo(origin);
			if (query.box() != null || distance <= query.radius()) {
				found.add(new Found(entity, pos, distance));
			}
		}
		found.sort(Comparator.comparingDouble(Found::distance));

		JsonArray entities = new JsonArray();
		for (Found entry : found.subList(0, Math.min(found.size(), query.limit()))) {
			entities.add(describe(level, player, view, entry, query.visibility()));
		}
		return entities;
	}

	private static JsonObject describe(ClientLevel level, LocalPlayer player, View view, Found found, boolean visibility) {
		Entity entity = found.entity();
		float partialTick = view.partialTick();
		JsonObject json = new JsonObject();
		json.addProperty("id", entity.getId());
		json.addProperty("type", Names.of(BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType())));
		json.addProperty("category", entity.getType().getCategory().getName());
		json.add("pos", vector(found.pos().x, found.pos().y, found.pos().z));
		// Movement during the last tick: the client moves entities itself, its getDeltaMovement() is often stale.
		json.add("motion", vector(entity.getX() - entity.xo, entity.getY() - entity.yo, entity.getZ() - entity.zo));
		json.addProperty("yaw", Mth.wrapDegrees(entity.getViewYRot(partialTick)));
		json.addProperty("pitch", entity.getViewXRot(partialTick));
		JsonArray size = new JsonArray();
		size.add(entity.getBbWidth());
		size.add(entity.getBbHeight());
		json.add("size", size);
		json.addProperty("distance", found.distance());
		json.addProperty("invisible", entity.isInvisible());
		if (entity.hasCustomName()) {
			json.addProperty("name", entity.getCustomName().getString());
		} else if (entity instanceof Player) {
			json.addProperty("name", entity.getName().getString());
		}
		if (entity instanceof LivingEntity living) {
			json.addProperty("health", living.getHealth());
			json.addProperty("max_health", living.getMaxHealth());
			json.addProperty("baby", living.isBaby());
		}
		if (entity instanceof ItemEntity item) {
			json.addProperty("item", Names.of(BuiltInRegistries.ITEM.getKey(item.getItem().getItem())));
			json.addProperty("count", item.getItem().getCount());
		}
		if (visibility) {
			AABB box = entity.getBoundingBox().move(found.pos().subtract(entity.position()));
			json.addProperty("line_of_sight", hasLineOfSight(level, player, view.camera(), box));
			json.addProperty("in_view", view.frustum().isVisible(box));
		}
		return json;
	}

	private static boolean hasLineOfSight(ClientLevel level, LocalPlayer player, Vec3 camera, AABB box) {
		Vec3 center = box.getCenter();
		for (double height : SIGHT_HEIGHTS) {
			Vec3 target = new Vec3(center.x, box.minY + height * box.getYsize(), center.z);
			ClipContext ray = new ClipContext(camera, target, ClipContext.Block.VISUAL, ClipContext.Fluid.NONE, player);
			if (level.clip(ray).getType() == HitResult.Type.MISS) {
				return true;
			}
		}
		return false;
	}

	private static JsonArray vector(double x, double y, double z) {
		JsonArray array = new JsonArray();
		array.add(x);
		array.add(y);
		array.add(z);
		return array;
	}
}
