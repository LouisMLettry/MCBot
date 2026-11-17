package com.mcbot;

import com.mcbot.net.BotServer;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Mod entry point: starts the local TCP server and hooks the controller on the client ticks and rendered frames.
 */
public class McBotClient implements ClientModInitializer {
	public static final String MOD_ID = "mcbot";
	public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

	/** Default port, can be changed with the JVM property -Dmcbot.port=XXXX. */
	public static final int DEFAULT_PORT = 5555;

	@Override
	public void onInitializeClient() {
		int port = Integer.getInteger("mcbot.port", DEFAULT_PORT);

		BotController controller = new BotController();
		ClientTickEvents.END_CLIENT_TICK.register(controller::onEndTick);
		WorldRenderEvents.END.register(controller::onWorldRendered);

		new BotServer(port, controller).start();
	}
}
