package com.mcbot;

/**
 * Expected error (bad parameter, impossible action…) sent as is to the Python program.
 */
public class BotException extends RuntimeException {
	public BotException(String message) {
		super(message);
	}
}
