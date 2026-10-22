package com.mcbot.net;

import com.google.gson.JsonObject;

/**
 * Réponse envoyée au programme Python : un objet JSON d'informations et, éventuellement, des données binaires
 * (image RGB brute ou blocs, selon le champ {@code payload} du JSON).
 */
public record BotResponse(JsonObject info, byte[] data) {
	public static BotResponse error(String message) {
		JsonObject info = new JsonObject();
		info.addProperty("ok", false);
		info.addProperty("error", message);
		return new BotResponse(info, null);
	}
}
