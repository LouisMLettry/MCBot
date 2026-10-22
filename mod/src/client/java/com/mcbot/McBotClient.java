package com.mcbot;

import com.mcbot.net.BotServer;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Point d'entrée du mod : démarre le serveur TCP local et branche le contrôleur sur les ticks du client.
 */
public class McBotClient implements ClientModInitializer {
	public static final String MOD_ID = "mcbot";
	public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

	/** Port par défaut, modifiable avec la propriété JVM -Dmcbot.port=XXXX. */
	public static final int DEFAULT_PORT = 5555;

	@Override
	public void onInitializeClient() {
		int port = Integer.getInteger("mcbot.port", DEFAULT_PORT);

		BotController controller = new BotController();
		ClientTickEvents.END_CLIENT_TICK.register(controller::onEndTick);

		new BotServer(port, controller).start();
	}
}
