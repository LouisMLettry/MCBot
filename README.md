# MinecraftBot

Piloter son personnage Minecraft depuis Python, avec les images du jeu, en vue d'y brancher du ML plus tard.

- `mod/` : mod **Fabric pour Minecraft 1.21.1** (côté client). Il ouvre un serveur TCP local (`127.0.0.1:5555`) qui reçoit des actions (avancer, tourner, sauter…) et renvoie l'état du joueur et, si demandé, une image du jeu.
- `python/` : client Python (`mcbot`) et script de démonstration `demo_movements.py`.
- `doc/` : documentation du système (architecture, journal, feuille de route).

## 1. Prérequis

- **JDK 25** pour compiler le mod (le plugin Gradle Fabric « Loom » l'exige ; le mod lui-même cible Java 21, comme Minecraft 1.21.1) :
  ```powershell
  winget install EclipseAdoptium.Temurin.25.JDK
  ```
  Rouvrir le terminal ensuite (`java -version` doit afficher 25 ou plus ; JDK 26 fonctionne aussi).
- **Python 3.10+** et **[uv](https://docs.astral.sh/uv/)** pour gérer l'environnement Python
  (les dépendances sont déclarées dans `python/pyproject.toml`) :
  ```powershell
  winget install astral-sh.uv
  ```

## 2. Mettre le mod dans Minecraft

### Option A — mode développement (le plus simple)
Lance un Minecraft déjà équipé du mod, sans passer par le launcher (compte hors ligne « Player… ») :
```powershell
cd mod
.\gradlew.bat runClient
```
Le premier lancement télécharge Minecraft et les dépendances (quelques minutes). Dans les logs, tu dois voir :
```
[McBot-Server/INFO] (mcbot) McBot listening on 127.0.0.1:5555
```

### Option B — dans ton Minecraft habituel (launcher officiel)
1. Compiler le mod :
   ```powershell
   cd mod
   .\gradlew.bat build
   ```
   → le fichier du mod est `mod\build\libs\mcbot-0.2.1.jar` (pas celui en `-sources`).
   Lors d'une mise à jour, supprimer l'ancien `mcbot-*.jar` du dossier `mods` avant de copier le nouveau.
2. Installer **Fabric Loader** pour 1.21.1 avec l'installeur officiel : <https://fabricmc.net/use/installer/> (onglet *Client*, version 1.21.1).
   Attention à ne pas choisir **1.21.11** : le mod exige exactement 1.21.1 et Fabric refuse de le charger sinon.
3. Télécharger **Fabric API** pour 1.21.1 : <https://modrinth.com/mod/fabric-api> (version `…+1.21.1`).
4. Copier `mcbot-0.2.1.jar` **et** le jar de Fabric API dans `%APPDATA%\.minecraft\mods` (créer le dossier s'il n'existe pas).
5. Dans le launcher, choisir le profil **fabric-loader-1.21.1** et jouer.

Astuce (macOS / Linux) : au lieu de copier le jar à chaque compilation, mettre dans `mods` un lien symbolique
vers le jar compilé ; il suffit ensuite de relancer Minecraft après un `./gradlew build` :
```bash
ln -s "$PWD/build/libs/mcbot-0.2.1.jar" ~/Library/Application\ Support/minecraft/mods/mcbot-0.2.1.jar   # depuis mod/
```
Lier le jar, pas tout le dossier `build/libs` (Fabric chargerait aussi le jar `-sources`). Le lien est à refaire
si la version du mod change, car elle fait partie du nom du fichier.

## 3. Faire bouger le personnage depuis Python

1. Dans Minecraft, créer/entrer dans un **monde solo** (idéalement *Superflat* pour avoir de la place).
2. Dans un autre terminal :
   ```powershell
   cd python
   uv sync
   uv run python demo_movements.py
   ```
   `uv sync` crée l'environnement `.venv` et installe les dépendances (à refaire après une mise à jour de
   `pyproject.toml`) ; `uv run` lance la commande dans cet environnement.
   Le personnage avance, tourne, saute, regarde en haut et en bas, marche en rond, sprinte…
   Des captures sont enregistrées dans `python/frames/`.

Tu peux cliquer sur le terminal : le mod désactive la mise en pause automatique pendant qu'un script est connecté (et ferme le menu Pause s'il est ouvert).

### Utiliser le client dans ton propre code
```python
from mcbot import MinecraftClient

with MinecraftClient() as mc:            # 127.0.0.1:5555
    mc.config(width=160, height=90)       # taille des images renvoyées
    image, info = mc.forward(seconds=1, frame=True)   # image : np.ndarray (90, 160, 3) uint8
    print(info["pos"], info["yaw"])
    mc.turn(90)                           # tourner de 90° à droite en 0,5 s
    mc.step(ticks=20, forward=True, jump=True, yaw=-45)   # action libre pendant 1 s
    mc.stop()                             # relâcher toutes les touches
```
Touches disponibles pour `step` : `forward, back, left, right, jump, sprint, sneak, attack, use`, plus `yaw` (degrés, > 0 = droite) et `pitch` (degrés, > 0 = vers le bas). 20 ticks = 1 seconde.
**Les touches restent enfoncées jusqu'à la commande suivante** (utile pour enchaîner des pas sans à-coups) ; `stop()` ou la déconnexion les relâchent.

## 4. Construction automatique

Le mod sait aussi :
1. passer en **mode construction** (créatif) — dans un monde solo, même sans les cheats ;
2. **voler** (en vol : `jump` = monter, `sneak` = descendre) ;
3. **choisir le bloc** en main (n'importe quel bloc du jeu en mode construction) ;
4. **poser** un bloc à des coordonnées précises (à portée : 5 blocs en créatif), et en **casser** un.

### Exemple : une petite maison
Se tenir **au sol** dans un monde solo (Superflat idéal), face à un espace libre, puis :
```powershell
cd python
uv run python build_house.py
```
Le personnage passe en créatif, s'envole, pose le sol, fait le tour des murs (fenêtres, porte, torche), construit un toit
en pyramide, puis recule pour photographier la maison (`python/frames/maison.png`). Environ 200 blocs, ~1 minute.
Option `--delay N` : ticks d'attente après chaque bloc (défaut 2 ; 0 = le plus rapide).

### Dans ton propre code
```python
from mcbot import Builder, MinecraftClient, Phase, Placement

with MinecraftClient() as mc:
    mc.set_build_mode(True)              # créatif ; set_build_mode(False) = survie
    mc.set_flying(True)
    mc.fly_to(10.5, -57, 3.5)            # vole jusqu'à cette position (pieds), puis s'arrête
    mc.select_block("oak_planks", slot=0)
    info = mc.place_block(10, -60, 6)    # info["placed"] : True / False (+ info["reason"])
    mc.place_block(11, -59, 6, face="north")   # face cliquée : oriente bûches, dalles, escaliers
    mc.break_block(10, -60, 6)

    # Ou en laissant le Builder voler à portée et changer de bloc tout seul :
    Builder(mc).build([
        Phase("Muret", standpoint=(0.5, -58, 0.5),
              blocks=[Placement((x, -60, 3), "cobblestone") for x in range(-2, 3)]),
    ])
```
- `place_block` ne nécessite pas de bloc voisin : on peut construire en l'air. Raisons d'échec possibles :
  `occupied`, `out_of_reach`, `no_block_selected`, `player_in_the_way`, `rejected`.
- Les identifiants de blocs sont ceux de Minecraft (`stone`, `oak_log`, `glass_pane`, `minecraft:red_wool`…).
- Le joueur regarde chaque bloc qu'il pose (désactivable avec `look=False`).

## 5. Protocole (pour info)
Entiers big-endian, une requête → une réponse :
- requête : `uint32 longueur` + JSON UTF-8 ;
- réponse : `uint32 longueur` + JSON, puis `uint32 longueur` + pixels RGB bruts (`hauteur × largeur × 3`, ligne par ligne depuis le haut ; longueur 0 si pas d'image).

| `type` | Champs | Effet |
|---|---|---|
| `ping` | — | Renvoie l'état. |
| `config` | `width`, `height`, `hide_gui` (optionnel) | Taille des images (16–1024 px) ; masquer l'interface comme F1. |
| `step` | `ticks`, `frame`, `action` {touches booléennes, `yaw`, `pitch`} | Applique l'action pendant `ticks` ticks puis répond. |
| `game_mode` | `mode` (`survival`, `creative`, `adventure`, `spectator`) | Change le mode de jeu (monde solo) ; répond une fois appliqué. |
| `fly` | `enabled` | Active/coupe le vol (créatif). Le vol est rallumé automatiquement s'il se coupe en l'air. |
| `select_block` | `block`, `slot` (0–8, optionnel) | Met le bloc en main (créé en créatif, cherché dans la barre sinon). |
| `place_block` | `x`, `y`, `z`, `face` (défaut `up`), `look` (défaut `true`) | Pose le bloc tenu → `placed`, `reason`, `message`, `block`. |
| `break_block` | `x`, `y`, `z`, `look` | Casse le bloc (créatif) → `broken`, `reason`, `block`. |

Réponse : `ok`, `error`, `tick`, `paused`, `screen`, `in_world`, `pos` [x, y, z], `motion` [vx, vy, vz] (blocs/tick), `yaw`, `pitch`, `on_ground`, `health`, `flying`, `may_fly`, `game_mode`, `reach`, `selected_slot`, `held_item`, `frame_width`, `frame_height`.

Le port peut être changé en lançant le jeu avec `-Dmcbot.port=XXXX`.

## Tests
```powershell
cd python
uv run pytest tests
```
Ils vérifient le client Python avec un faux serveur (dont une simulation de la physique du vol pour `fly_to`) et le plan de la maison (tout est à portée, le joueur ne gêne jamais), sans lancer Minecraft.
