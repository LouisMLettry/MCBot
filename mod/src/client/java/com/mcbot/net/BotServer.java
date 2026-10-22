package com.mcbot.net;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mcbot.BotController;
import com.mcbot.McBotClient;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

/**
 * Serveur TCP (127.0.0.1 uniquement) qui reçoit les commandes du programme Python.
 *
 * <p>Protocole, entiers en big-endian :
 * <ul>
 *   <li>requête : {@code uint32 longueur} + JSON UTF-8 ;</li>
 *   <li>réponse : {@code uint32 longueur} + JSON UTF-8, puis {@code uint32 longueur} + image RGB brute (0 si aucune).</li>
 * </ul>
 * Un seul client à la fois ; les requêtes sont traitées dans l'ordre, sur le thread du jeu.
 */
public class BotServer implements Runnable {
	private static final int MAX_MESSAGE_SIZE = 1 << 20;
	private static final long REQUEST_TIMEOUT_SECONDS = 120;

	private final int port;
	private final BotController controller;

	public BotServer(int port, BotController controller) {
		this.port = port;
		this.controller = controller;
	}

	public void start() {
		Thread thread = new Thread(this, "McBot-Server");
		thread.setDaemon(true);
		thread.start();
	}

	@Override
	public void run() {
		try (ServerSocket server = new ServerSocket(port, 1, InetAddress.getLoopbackAddress())) {
			McBotClient.LOGGER.info("McBot listening on 127.0.0.1:{}", port);
			while (!Thread.currentThread().isInterrupted()) {
				try (Socket socket = server.accept()) {
					socket.setTcpNoDelay(true);
					McBotClient.LOGGER.info("McBot client connected from {}", socket.getRemoteSocketAddress());
					handleClient(socket);
					McBotClient.LOGGER.info("McBot client disconnected");
				} catch (IOException e) {
					McBotClient.LOGGER.info("McBot client connection closed: {}", e.getMessage());
				} finally {
					controller.releaseAll();
				}
			}
		} catch (IOException e) {
			McBotClient.LOGGER.error("Unable to start McBot server on port {}", port, e);
		}
	}

	private void handleClient(Socket socket) throws IOException {
		DataInputStream in = new DataInputStream(new BufferedInputStream(socket.getInputStream()));
		DataOutputStream out = new DataOutputStream(new BufferedOutputStream(socket.getOutputStream()));

		while (true) {
			int length;
			try {
				length = in.readInt();
			} catch (EOFException e) {
				return;
			}
			if (length < 0 || length > MAX_MESSAGE_SIZE) {
				throw new IOException("Invalid message length: " + length);
			}
			byte[] payload = new byte[length];
			in.readFully(payload);

			BotResponse response;
			try {
				JsonObject request = JsonParser.parseString(new String(payload, StandardCharsets.UTF_8)).getAsJsonObject();
				response = controller.submit(request).get(REQUEST_TIMEOUT_SECONDS, TimeUnit.SECONDS);
			} catch (ExecutionException e) {
				response = BotResponse.error(String.valueOf(e.getCause()));
			} catch (Exception e) {
				response = BotResponse.error(e.toString());
			}
			write(out, response);
		}
	}

	private static void write(DataOutputStream out, BotResponse response) throws IOException {
		byte[] json = response.info().toString().getBytes(StandardCharsets.UTF_8);
		byte[] frame = response.frame() == null ? new byte[0] : response.frame();
		out.writeInt(json.length);
		out.write(json);
		out.writeInt(frame.length);
		out.write(frame);
		out.flush();
	}
}
