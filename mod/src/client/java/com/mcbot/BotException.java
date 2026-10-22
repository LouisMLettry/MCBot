package com.mcbot;

/**
 * Erreur attendue (mauvais paramètre, action impossible…) renvoyée telle quelle au programme Python.
 */
public class BotException extends RuntimeException {
	public BotException(String message) {
		super(message);
	}
}
