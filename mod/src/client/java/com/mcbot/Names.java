package com.mcbot;

import net.minecraft.resources.ResourceLocation;

/**
 * Block and item names sent to the Python program: without the {@code minecraft:} namespace
 * ({@code stone}, {@code oak_log[axis=y]}). The project assumes Minecraft without other mods adding blocks.
 */
public final class Names {
	private static final String VANILLA_PREFIX = ResourceLocation.DEFAULT_NAMESPACE + ":";

	private Names() {
	}

	public static String of(ResourceLocation id) {
		return shorten(id.toString());
	}

	/** Removes {@code minecraft:} from the start of an identifier, possibly followed by a state ({@code [axis=y]}). */
	public static String shorten(String id) {
		return id.startsWith(VANILLA_PREFIX) ? id.substring(VANILLA_PREFIX.length()) : id;
	}
}
