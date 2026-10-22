package com.mcbot.capture;

import com.mojang.blaze3d.platform.NativeImage;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;

/**
 * Captures the image displayed by the game and shrinks it to the requested size.
 */
public final class FrameCapture {
	private FrameCapture() {
	}

	/**
	 * Reads the last rendered image and shrinks it by averaging blocks of pixels.
	 * Must be called on the render thread (which is the case during a client tick).
	 *
	 * @return the pixels in RGB, row by row from the top ({@code height * width * 3} bytes)
	 */
	public static byte[] capture(Minecraft client, int width, int height) {
		try (NativeImage image = Screenshot.takeScreenshot(client.getMainRenderTarget())) {
			int srcWidth = image.getWidth();
			int srcHeight = image.getHeight();
			byte[] rgb = new byte[width * height * 3];
			int i = 0;

			for (int y = 0; y < height; y++) {
				int y0 = y * srcHeight / height;
				int y1 = Math.max(y0 + 1, (y + 1) * srcHeight / height);
				for (int x = 0; x < width; x++) {
					int x0 = x * srcWidth / width;
					int x1 = Math.max(x0 + 1, (x + 1) * srcWidth / width);

					long r = 0, g = 0, b = 0;
					for (int sy = y0; sy < y1; sy++) {
						for (int sx = x0; sx < x1; sx++) {
							// Despite its name, getPixelRGBA returns ABGR: red is in the least significant byte.
							int pixel = image.getPixelRGBA(sx, sy);
							r += pixel & 0xFF;
							g += (pixel >> 8) & 0xFF;
							b += (pixel >> 16) & 0xFF;
						}
					}
					int count = (y1 - y0) * (x1 - x0);
					rgb[i++] = (byte) (r / count);
					rgb[i++] = (byte) (g / count);
					rgb[i++] = (byte) (b / count);
				}
			}
			return rgb;
		}
	}
}
