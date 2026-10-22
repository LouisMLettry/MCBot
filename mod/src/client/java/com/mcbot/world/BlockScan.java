package com.mcbot.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mcbot.BotException;
import com.mcbot.Names;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.SectionPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.level.block.state.BlockState;

import java.nio.ByteBuffer;
import java.util.HashMap;
import java.util.Map;

/**
 * Reads the blocks of a box of the world, as the client knows it (loaded chunks, within render distance).
 * Must be called on the game thread.
 *
 * <p>Result: a palette of block names (in the JSON) and, for each block, its index in the palette
 * ({@code uint16} big-endian, in the binary part). Blocks are ordered by x, then y, then z: block
 * (x, y, z) is at index {@code ((x - minX) * sizeY + (y - minY)) * sizeZ + (z - minZ)}.
 */
public final class BlockScan {
	/** Maximum number of blocks per request (2 MB of data), enough to read 3 × 3 whole chunks. */
	public static final int MAX_BLOCKS = 1 << 20;

	public record Result(JsonObject info, byte[] data) {
	}

	private BlockScan() {
	}

	/** Whole chunk (16 × world height × 16) at chunk coordinates ({@code chunkX}, {@code chunkZ}). */
	public static Result scanChunk(ClientLevel level, int chunkX, int chunkZ, boolean states) {
		int x = SectionPos.sectionToBlockCoord(chunkX);
		int z = SectionPos.sectionToBlockCoord(chunkZ);
		return scan(level, new BlockPos(x, level.getMinBuildHeight(), z),
				new BlockPos(x + 15, level.getMaxBuildHeight() - 1, z + 15), states);
	}

	/**
	 * Box between two corners (included), limited to the world height. With {@code states}, the palette holds the full
	 * state of the blocks ({@code oak_log[axis=y]}) instead of just their name.
	 */
	public static Result scan(ClientLevel level, BlockPos corner1, BlockPos corner2, boolean states) {
		int minX = Math.min(corner1.getX(), corner2.getX());
		int maxX = Math.max(corner1.getX(), corner2.getX());
		int minZ = Math.min(corner1.getZ(), corner2.getZ());
		int maxZ = Math.max(corner1.getZ(), corner2.getZ());
		int minY = Math.max(Math.min(corner1.getY(), corner2.getY()), level.getMinBuildHeight());
		int maxY = Math.min(Math.max(corner1.getY(), corner2.getY()), level.getMaxBuildHeight() - 1);
		if (minY > maxY) {
			throw new BotException("The box is outside the world height (" + level.getMinBuildHeight() + " to "
					+ (level.getMaxBuildHeight() - 1) + ")");
		}

		long sizeX = maxX - minX + 1L;
		long sizeY = maxY - minY + 1L;
		long sizeZ = maxZ - minZ + 1L;
		long volume = sizeX * sizeY * sizeZ;
		if (volume > MAX_BLOCKS) {
			throw new BotException("Box too large: " + volume + " blocks (max " + MAX_BLOCKS + ")");
		}
		requireLoaded(level, minX, minZ, maxX, maxZ);

		Map<Object, Integer> indices = new HashMap<>();
		JsonArray palette = new JsonArray();
		ByteBuffer data = ByteBuffer.allocate((int) volume * 2); // big-endian by default
		BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();

		for (int x = minX; x <= maxX; x++) {
			for (int y = minY; y <= maxY; y++) {
				for (int z = minZ; z <= maxZ; z++) {
					BlockState state = level.getBlockState(pos.set(x, y, z));
					Object key = states ? state : state.getBlock();
					Integer index = indices.get(key);
					if (index == null) {
						index = palette.size();
						indices.put(key, index);
						palette.add(states ? Names.shorten(BlockStateParser.serialize(state))
								: Names.of(BuiltInRegistries.BLOCK.getKey(state.getBlock())));
					}
					data.putShort((short) index.intValue());
				}
			}
		}

		JsonObject info = new JsonObject();
		info.addProperty("payload", "blocks");
		info.add("origin", vector(minX, minY, minZ));
		info.add("shape", vector(sizeX, sizeY, sizeZ));
		info.add("palette", palette);
		return new Result(info, data.array());
	}

	private static void requireLoaded(ClientLevel level, int minX, int minZ, int maxX, int maxZ) {
		for (int chunkX = SectionPos.blockToSectionCoord(minX); chunkX <= SectionPos.blockToSectionCoord(maxX); chunkX++) {
			for (int chunkZ = SectionPos.blockToSectionCoord(minZ); chunkZ <= SectionPos.blockToSectionCoord(maxZ); chunkZ++) {
				if (!level.getChunkSource().hasChunk(chunkX, chunkZ)) {
					throw new BotException("Chunk (" + chunkX + ", " + chunkZ + ") is not loaded (outside render distance)");
				}
			}
		}
	}

	private static JsonArray vector(long x, long y, long z) {
		JsonArray array = new JsonArray();
		array.add(x);
		array.add(y);
		array.add(z);
		return array;
	}
}
