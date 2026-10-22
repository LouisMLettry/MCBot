package com.mcbot.net;

import com.google.gson.JsonObject;

/**
 * Réponse envoyée au programme Python : un objet JSON d'informations et, éventuellement, une image RGB brute.
 */
public record BotResponse(JsonObject info, byte[] frame) {
	public static BotResponse error(String message) {
		JsonObject info = new JsonObject();
		info.addProperty("ok", false);
		info.addProperty("error", message);
		return new BotResponse(info, null);
	}
}
