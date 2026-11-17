package com.mcbot.world;

import com.google.gson.JsonArray;
import com.mcbot.BotException;
import com.mcbot.Names;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.SectionPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;

/**
 * Writes exact block states ({@code oak_stairs[facing=east,half=bottom]}) through the singleplayer server, like the
 * {@code /setblock} command but without cheats. Blocks are written as given: neighbouring blocks are not updated,
 * so a torch written before its wall stays in place.
 *
 * <p>Only cells in chunks the client has loaded can be written: the server never has to load or generate a chunk,
 * and the client can show the result.
 */
public final class BlockWriter {
	/** Write without updating the shape of neighbouring blocks, and send the change to the client. */
	private static final int FLAGS = Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;

	private BlockWriter() {
	}

	public static BlockState parse(String text) {
		try {
			return BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK.asLookup(), text, false).blockState();
		} catch (CommandSyntaxException e) {
			throw new BotException("Invalid block state '" + text + "': " + e.getMessage());
		}
	}

	/** Must be called on the game thread; the returned future completes once the server has written every block. */
	public static CompletableFuture<Void> write(Minecraft client, List<BlockPos> positions, List<BlockState> states) {
		IntegratedServer server = client.getSingleplayerServer();
		if (server == null) {
			throw new BotException("Writing blocks requires a singleplayer world");
		}
		Set<Long> loaded = new HashSet<>();
		for (BlockPos pos : positions) {
			if (client.level.isOutsideBuildHeight(pos)) {
				throw new BotException("Position outside the world height: " + pos.toShortString());
			}
			int chunkX = SectionPos.blockToSectionCoord(pos.getX());
			int chunkZ = SectionPos.blockToSectionCoord(pos.getZ());
			if (loaded.add(ChunkPos.asLong(chunkX, chunkZ)) && !client.level.getChunkSource().hasChunk(chunkX, chunkZ)) {
				throw new BotException("Chunk (" + chunkX + ", " + chunkZ + ") is not loaded (outside render distance): "
						+ pos.toShortString());
			}
		}
		ResourceKey<Level> dimension = client.level.dimension();
		CompletableFuture<Void> written = new CompletableFuture<>();
		server.execute(() -> {
			try {
				ServerLevel level = server.getLevel(dimension);
				for (int i = 0; i < positions.size(); i++) {
					level.setBlock(positions.get(i), states.get(i), FLAGS);
				}
				written.complete(null);
			} catch (RuntimeException e) {
				written.completeExceptionally(e);
			}
		});
		return written;
	}

	/** True once the client shows every written block (the server sends the changes at the end of its tick). */
	public static boolean isVisible(ClientLevel level, List<BlockPos> positions, List<BlockState> states) {
		for (int i = 0; i < positions.size(); i++) {
			if (level.getBlockState(positions.get(i)) != states.get(i)) {
				return false;
			}
		}
		return true;
	}

	/**
	 * Cells where the client shows another state than the one written, as [[x, y, z, "state now"], …]: blocks the
	 * game changed on its own right after they were written (falling sand, a redstone wire without support…).
	 */
	public static JsonArray changes(ClientLevel level, List<BlockPos> positions, List<BlockState> states) {
		JsonArray changes = new JsonArray();
		for (int i = 0; i < positions.size(); i++) {
			BlockPos pos = positions.get(i);
			BlockState now = level.getBlockState(pos);
			if (now != states.get(i)) {
				JsonArray change = new JsonArray();
				change.add(pos.getX());
				change.add(pos.getY());
				change.add(pos.getZ());
				change.add(Names.shorten(BlockStateParser.serialize(now)));
				changes.add(change);
			}
		}
		return changes;
	}

	public static JsonArray names(List<BlockState> states) {
		JsonArray names = new JsonArray();
		for (BlockState state : states) {
			names.add(Names.shorten(BlockStateParser.serialize(state)));
		}
		return names;
	}
}
