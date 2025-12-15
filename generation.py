import random
import math
from dataclasses import dataclass
from noise import pnoise2, snoise3
from minecraft import MinecraftWorld, CustomBiome, IntColor

# --- Configuration ---
NUM_ISLANDS = 30
ISLAND_RADIUS_MIN = 16
ISLAND_RADIUS_MAX = 256
ISLAND_Y_LEVEL = 60
ISLAND_SPREAD = 500

# Standard biomes
STANDARD_BIOMES = [
    'minecraft:plains',
    'minecraft:forest',
    'minecraft:desert',
    'minecraft:taiga',
    'minecraft:swamp',
    'minecraft:savanna',
    'minecraft:jungle',
    'minecraft:snowy_plains',
    'minecraft:badlands',
    'minecraft:dark_forest'
]

# --- Noise Settings ---
SEED = 12345
SCALE_TOP = 0.04
SCALE_BOTTOM = 0.15
SCALE_CAVE = 0.06
CAVE_THRESHOLD = 0.55

# --- Data Structures ---
@dataclass
class IslandData:
    x: int
    z: int
    radius: int
    biome: str
    has_lake: bool
    water_level: int
    liquid_block: str

def get_height_map(x, z, seed, scale):
    return pnoise2((x + seed) * scale, (z + seed) * scale, 
                   octaves=4, persistence=0.5, lacunarity=2.0)

def get_cave_density(x, y, z, seed, scale):
    return snoise3((x + seed) * scale, (y + seed) * scale, (z + seed) * scale, 
                   octaves=2, persistence=0.5, lacunarity=2.0)

def create_volcanic_biome():
    volcanic = CustomBiome('volcanic_biome')
    volcanic.set_colors(
        sky=IntColor.from_hex("#111111"),
        water=IntColor.from_hex("#D6D6D6"),
        fog=IntColor.from_hex("#111111"),
        water_fog=IntColor.from_hex("#FFFFFF"),
        grass=IntColor.from_hex("#363636")
    )
    volcanic.set_particles("minecraft:white_ash", probability=0.1)
    return volcanic

def generate_island_layout(biome_liquid_map, spawn_r_override=None):
    print("Calculating island layout...")
    islands_layout = []
    available_biomes = list(biome_liquid_map.keys())

    # 1. Spawn Island (Safe Plains)
    spawn_r = spawn_r_override if spawn_r_override else random.randint(ISLAND_RADIUS_MIN, ISLAND_RADIUS_MAX)
    spawn_island = IslandData(
        x=0, z=0, radius=spawn_r, 
        biome='minecraft:plains', 
        has_lake=True, 
        water_level=ISLAND_Y_LEVEL - 2,
        liquid_block='minecraft:water'
    )
    islands_layout.append(spawn_island)
    
    # 2. Generate others
    attempts = 0
    while len(islands_layout) < NUM_ISLANDS and attempts < 5000:
        attempts += 1
        cx = random.randint(-ISLAND_SPREAD, ISLAND_SPREAD)
        cz = random.randint(-ISLAND_SPREAD, ISLAND_SPREAD)
        cr = random.randint(ISLAND_RADIUS_MIN, ISLAND_RADIUS_MAX)
        
        collision = False
        for island in islands_layout:
            dist = math.sqrt((cx - island.x)**2 + (cz - island.z)**2)
            if dist < (cr + island.radius + 15):
                collision = True
                break
        
        if not collision:
            chosen_biome = random.choice(available_biomes)
            chosen_liquid = biome_liquid_map[chosen_biome]
            has_lake = random.choice([True, False])
            water_lvl = (ISLAND_Y_LEVEL + random.randint(-3, 2)) if has_lake else -999
            
            new_island = IslandData(cx, cz, cr, chosen_biome, has_lake, water_lvl, chosen_liquid)
            islands_layout.append(new_island)
            
    return islands_layout

def generate_islands(mc_world, island_layout_list):
    spawn_y = ISLAND_Y_LEVEL 
    print(f"Generating blocks for {len(island_layout_list)} islands...")

    for i, island in enumerate(island_layout_list):
        print(f"  - Island {i+1} ({island.biome})")

        # --- 1. Biome Strips ---
        for z in range(island.z - island.radius, island.z + island.radius + 1):
            dz = z - island.z
            if abs(dz) <= island.radius:
                width_half = int(math.sqrt(island.radius**2 - dz**2))
                mc_world.fill_biomes(
                    (island.x - width_half, -64, z), 
                    (island.x + width_half, 320, z), 
                    island.biome
                )

        # --- 2. Block Placement ---
        for x in range(island.x - island.radius, island.x + island.radius + 1):
            for z in range(island.z - island.radius, island.z + island.radius + 1):
                
                dist = math.sqrt((x - island.x)**2 + (z - island.z)**2)
                if dist > island.radius: continue

                # Calculate Heights
                noise_val = get_height_map(x, z, SEED, SCALE_TOP)
                top_y = ISLAND_Y_LEVEL + int(noise_val * 10)

                if (1.0 - dist/island.radius) < 0.2:
                    top_y -= int((0.2 - (1.0 - dist/island.radius)) * 15)

                if island.has_lake and dist > (island.radius * 0.85):
                    if top_y < island.water_level + 1: top_y = island.water_level + 1

                norm_dist = dist / island.radius
                current_depth = math.sqrt(max(0, 1.0 - norm_dist**2)) * 35
                ragged_noise = get_height_map(x, z, SEED + 100, SCALE_BOTTOM) * 8
                bottom_y = int(top_y - current_depth + ragged_noise)
                
                if bottom_y >= top_y: continue

                # Place Column
                for y in range(bottom_y, top_y + 1):
                    # Cave Check
                    cave_noise = get_cave_density(x, y, z, SEED + 200, SCALE_CAVE)
                    if cave_noise > CAVE_THRESHOLD and y <= island.water_level - 3:
                        continue 

                    # A. Determine Standard Block
                    depth = top_y - y
                    block_type = 'minecraft:stone' 

                    if depth == 0:
                        if y < island.water_level:
                            block_type = 'minecraft:dirt' # Lake bed
                        else:
                            block_type = 'minecraft:grass_block'
                    elif depth < 5:
                        block_type = 'minecraft:dirt'
                    elif depth < 15:
                        block_type = 'minecraft:stone'
                    else:
                        block_type = 'minecraft:deepslate'

                    # B. Apply Biome Overrides
                    
                    # --- Desert Override ---
                    if island.biome == 'minecraft:desert':
                        if block_type == 'minecraft:grass_block':
                            block_type = 'minecraft:sand'
                        elif block_type == 'minecraft:dirt':
                            block_type = 'minecraft:sandstone'
                    
                    # --- Volcanic Override ---
                    elif 'volcanic_biome' in island.biome:
                        # 1. Randomly replace Grass/Dirt with Gravel
                        if block_type in ['minecraft:grass_block', 'minecraft:dirt']:
                            if random.random() < 0.25: # 25% chance
                                block_type = 'minecraft:gravel'
                        
                        # 2. Randomly replace Deepslate with Obsidian
                        elif block_type == 'minecraft:deepslate':
                            if random.random() < 0.15: # 15% chance
                                block_type = 'minecraft:obsidian'

                    mc_world.set_block((x, y, z), block_type)

                # Liquid & Decoration
                if top_y < island.water_level:
                    mc_world.fill_blocks((x, top_y + 1, z), (x, island.water_level, z), island.liquid_block)
                elif top_y >= island.water_level:
                    # Only add grass foliage if the surface is actually grass
                    # (Volcanic might have swapped it to gravel, Desert swapped it to sand)
                    surface_block = mc_world.get_block((x, top_y, z))
                    if surface_block == 'minecraft:grass_block':
                        if random.random() < 0.25:
                            mc_world.set_block((x, top_y + 1, z), 'minecraft:grass')

                if x == 0 and z == 0:
                    spawn_y = max(top_y, island.water_level) + 2
                    
    return spawn_y

def main():
    mc_world = MinecraftWorld(world_name="Detailed Floating Islands")
    
    volcanic_biome = create_volcanic_biome()
    mc_world.add_biome(volcanic_biome)
    print(f"Registered custom biome: {volcanic_biome.full_name}")

    biome_liquids = {biome: 'minecraft:water' for biome in STANDARD_BIOMES}
    biome_liquids[volcanic_biome.full_name] = 'minecraft:lava'
    
    island_layout = generate_island_layout(biome_liquid_map=biome_liquids, spawn_r_override=256)
    spawn_y = generate_islands(mc_world, island_layout)

    mc_world.set_spawn((0, spawn_y, 0))
    print("Exporting world...")
    mc_world.export('detailed_floating_islands')
    print("Done!")

if __name__ == "__main__":
    main()