# Images

## Get a picture

Any movement command returns an image with `frame=True`:

```python
image, info = mc.step(ticks=1, frame=True)
image.shape, image.dtype       # (128, 128, 3) uint8, RGB, top row first
```

Without `frame=True`, `image` is `None`: images cost time, so only ask for them when you need them.

## Choose the size

[`config`][mcbot.MinecraftClient.config] sets the size of every image that follows, from 16 to 1024 pixels per
side. The whole game window is shrunk (or stretched) to that size by averaging pixels:

```python
mc.config(width=160, height=90)
```

Keep the **aspect ratio of the game window** (16:9 for the default window, 854 × 480) or the images will be
distorted. Small images are faster to send and often enough for learning: 84 × 84 or 160 × 90 are common choices.

## Hide the interface

The hotbar, crosshair, hand and chat are part of the picture. To remove them (like pressing F1):

```python
mc.config(width=320, height=180, hide_gui=True)
```

`hide_gui=False` shows them again.

## Save or use the image

```python
from PIL import Image

Image.fromarray(image).save("view.png")     # Pillow

import cv2                                  # OpenCV expects BGR
cv2.imwrite("view.png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))

import torch                                # PyTorch: channels first, floats in [0, 1]
tensor = torch.from_numpy(image).permute(2, 0, 1).float() / 255
```

## When an image is taken

The game updates the world 20 times per second (ticks) and draws frames in between. The image returned is the
**last frame drawn** at the end of the step. In practice:

- the state in `info` can be **up to one tick ahead** of the image (under 0.3 blocks at walking speed);
- with `ticks=0`, no frame is drawn during the step: the image comes from **before** it and does not show the
  rotation the step applied. Use `ticks=1` or more when the image must show the result of the action.

Entities requested together with an image (`entities=...`) are listed as the image shows them, not as `info`
does. Details: [When an image is taken](../concepts/time.md#when-an-image-is-taken).
