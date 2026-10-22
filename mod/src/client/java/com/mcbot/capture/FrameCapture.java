package com.mcbot.capture;

import com.mojang.blaze3d.platform.NativeImage;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;

/**
 * Capture l'image affichée par le jeu et la réduit à la taille demandée.
 */
public final class FrameCapture {
	private FrameCapture() {
	}

	/**
	 * Lit la dernière image rendue et la réduit par moyenne de blocs de pixels.
	 * Doit être appelé sur le thread de rendu (c'est le cas pendant un tick client).
	 *
	 * @return les pixels en RGB, ligne par ligne depuis le haut ({@code height * width * 3} octets)
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
							// Malgré son nom, getPixelRGBA renvoie le format ABGR : rouge dans l'octet de poids faible.
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
