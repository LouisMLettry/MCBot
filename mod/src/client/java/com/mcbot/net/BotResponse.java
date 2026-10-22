package com.mcbot.net;

import com.google.gson.JsonObject;

/**
 * Response sent to the Python program: a JSON object of information and, optionally, binary data
 * (raw RGB image or blocks, depending on the {@code payload} field of the JSON).
 */
public record BotResponse(JsonObject info, byte[] data) {
	public static BotResponse error(String message) {
		JsonObject info = new JsonObject();
		info.addProperty("ok", false);
		info.addProperty("error", message);
		return new BotResponse(info, null);
	}
}
