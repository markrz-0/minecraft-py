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
    'minecraft:dark_forest',
    'minecraft:birch_forest',
    'minecraft:cherry_grove'
]

# --- Flower Configuration ---
BIOME_FLOWERS = {
    'swamp': ['minecraft:blue_orchid'],
    'plains': [
        'minecraft:dandelion', 'minecraft:poppy', 'minecraft:azure_bluet', 
        'minecraft:oxeye_daisy', 'minecraft:cornflower', 
        'minecraft:orange_tulip', 'minecraft:red_tulip', 'minecraft:pink_tulip', 'minecraft:white_tulip'
    ],
    'forest': ['minecraft:dandelion', 'minecraft:poppy', 'minecraft:lilac', 'minecraft:rose_bush'],
    'jungle': ['minecraft:poppy', 'minecraft:dandelion'],
    'birch': ['minecraft:dandelion', 'minecraft:poppy', 'minecraft:lilac'],
    'dark_forest': ['minecraft:rose_bush', 'minecraft:peony', 'minecraft:lily_of_the_valley'],
    'cherry': ['minecraft:pink_petals'],
    'taiga': ['minecraft:fern', 'minecraft:sweet_berry_bush'], 
    'snowy': ['minecraft:dandelion', 'minecraft:poppy']
}

DEFAULT_FLOWERS = ['minecraft:dandelion', 'minecraft:poppy']

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

# --- Helper: Terrain Calculation ---
def calculate_surface_y(x, z, island):
    dist = math.sqrt((x - island.x)**2 + (z - island.z)**2)
    noise_val = get_height_map(x, z, SEED, SCALE_TOP)
    y = ISLAND_Y_LEVEL + int(noise_val * 10)

    if dist > island.radius: return -999
    
    edge_factor = 1.0 - (dist / island.radius)
    if edge_factor < 0.2:
        y -= int((0.2 - edge_factor) * 15)

    if island.has_lake and dist > (island.radius * 0.85):
        min_safe_height = island.water_level + 1
        if y < min_safe_height:
            y = min_safe_height
            
    return y

# --- Vegetation Logic ---

def place_tree(mc_world, x, y, z, biome_name):
    """Procedurally generates a tree."""
    log_type = 'minecraft:oak_log'
    leaf_type = 'minecraft:oak_leaves'
    tree_shape = 'standard' 

    if 'spruce' in biome_name or 'taiga' in biome_name or 'snowy' in biome_name:
        log_type = 'minecraft:spruce_log'
        leaf_type = 'minecraft:spruce_leaves'
        tree_shape = 'pine'
    elif 'birch' in biome_name:
        log_type = 'minecraft:birch_log'
        leaf_type = 'minecraft:birch_leaves'
    elif 'jungle' in biome_name:
        log_type = 'minecraft:jungle_log'
        leaf_type = 'minecraft:jungle_leaves'
    elif 'acacia' in biome_name or 'savanna' in biome_name:
        log_type = 'minecraft:acacia_log'
        leaf_type = 'minecraft:acacia_leaves'
    elif 'dark_forest' in biome_name:
        log_type = 'minecraft:dark_oak_log'
        leaf_type = 'minecraft:dark_oak_leaves'
    elif 'cherry' in biome_name:
        log_type = 'minecraft:cherry_log'
        leaf_type = 'minecraft:cherry_leaves'
    
    if tree_shape == 'standard':
        height = random.randint(4, 6)
        mc_world.fill_blocks((x, y, z), (x, y + height - 1, z), log_type)
        leaf_start = y + height - 2
        for ly in range(leaf_start, leaf_start + 4):
            radius = 2 if ly < leaf_start + 2 else 1
            for lx in range(x - radius, x + radius + 1):
                for lz in range(z - radius, z + radius + 1):
                    if lx == x and lz == z and ly < y + height: continue
                    if abs(lx-x) == radius and abs(lz-z) == radius and random.random() > 0.2: continue
                    mc_world.set_block((lx, ly, lz), leaf_type)
                    
    elif tree_shape == 'pine':
        height = random.randint(6, 9)
        mc_world.fill_blocks((x, y, z), (x, y + height - 1, z), log_type)
        leaf_start = y + 2
        current_radius = 2
        for ly in range(leaf_start, y + height + 2):
            for lx in range(x - current_radius, x + current_radius + 1):
                for lz in range(z - current_radius, z + current_radius + 1):
                    if lx == x and lz == z and ly < y + height: continue
                    d = math.sqrt((lx-x)**2 + (lz-z)**2)
                    if d <= current_radius + 0.5:
                        mc_world.set_block((lx, ly, lz), leaf_type)
            if (ly - leaf_start) % 2 == 1:
                current_radius -= 1
                if current_radius < 0: current_radius = 0

def place_cactus(mc_world, x, y, z):
    height = random.randint(1, 3)
    mc_world.fill_blocks((x, y + 1, z), (x, y + height, z), 'minecraft:cactus')

def place_sugarcane(mc_world, x, y, z):
    height = random.randint(2, 3)
    mc_world.fill_blocks((x, y + 1, z), (x, y + height, z), 'minecraft:sugar_cane')

def get_random_flower(biome_name):
    possible_flowers = DEFAULT_FLOWERS
    for key, flowers in BIOME_FLOWERS.items():
        if key in biome_name:
            possible_flowers = flowers
            break
    return random.choice(possible_flowers)

# --- Main Generation Logic ---

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

    spawn_r = spawn_r_override if spawn_r_override else random.randint(ISLAND_RADIUS_MIN, ISLAND_RADIUS_MAX)
    spawn_island = IslandData(
        x=0, z=0, radius=spawn_r, 
        biome='minecraft:plains', 
        has_lake=True, 
        water_level=ISLAND_Y_LEVEL - 2,
        liquid_block='minecraft:water'
    )
    islands_layout.append(spawn_island)
    
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

        # 1. Biome Strips
        for z in range(island.z - island.radius, island.z + island.radius + 1):
            dz = z - island.z
            if abs(dz) <= island.radius:
                width_half = int(math.sqrt(island.radius**2 - dz**2))
                mc_world.fill_biomes(
                    (island.x - width_half, -64, z), 
                    (island.x + width_half, 320, z), 
                    island.biome
                )

        # 2. Block Placement
        for x in range(island.x - island.radius, island.x + island.radius + 1):
            for z in range(island.z - island.radius, island.z + island.radius + 1):
                
                dist = math.sqrt((x - island.x)**2 + (z - island.z)**2)
                if dist > island.radius: continue

                # Height Calc
                top_y = calculate_surface_y(x, z, island)

                norm_dist = dist / island.radius
                current_depth = math.sqrt(max(0, 1.0 - norm_dist**2)) * 35
                ragged_noise = get_height_map(x, z, SEED + 100, SCALE_BOTTOM) * 8
                bottom_y = int(top_y - current_depth + ragged_noise)
                
                if bottom_y >= top_y: continue

                # Place Column
                for y in range(bottom_y, top_y + 1):
                    cave_noise = get_cave_density(x, y, z, SEED + 200, SCALE_CAVE)
                    if cave_noise > CAVE_THRESHOLD and y <= island.water_level - 3:
                        continue 

                    depth = top_y - y
                    block_type = 'minecraft:stone' 

                    if depth == 0:
                        if y < island.water_level: block_type = 'minecraft:dirt' 
                        else: block_type = 'minecraft:grass_block'
                    elif depth < 5: block_type = 'minecraft:dirt'
                    elif depth < 15: block_type = 'minecraft:stone'
                    else: block_type = 'minecraft:deepslate'

                    # Swaps
                    if island.biome == 'minecraft:desert':
                        if block_type == 'minecraft:grass_block': block_type = 'minecraft:sand'
                        elif block_type == 'minecraft:dirt': block_type = 'minecraft:sandstone'
                    elif 'volcanic_biome' in island.biome:
                        if block_type in ['minecraft:grass_block', 'minecraft:dirt'] and random.random() < 0.25:
                            block_type = 'minecraft:gravel'
                        elif block_type == 'minecraft:deepslate' and random.random() < 0.15:
                            block_type = 'minecraft:obsidian'

                    mc_world.set_block((x, y, z), block_type)

                # 3. Liquids & Surface Decoration
                if top_y < island.water_level:
                    mc_world.fill_blocks((x, top_y + 1, z), (x, island.water_level, z), island.liquid_block)
                
                elif top_y >= island.water_level:
                    surface_block = mc_world.get_block((x, top_y, z))
                    
                    # --- VEGETATION LOGIC ---
                    if 'volcanic_biome' in island.biome:
                        pass
                    
                    # B. Sugarcane
                    elif island.liquid_block == 'minecraft:water' and \
                         top_y == island.water_level and \
                         surface_block in ['minecraft:grass_block', 'minecraft:sand', 'minecraft:dirt']:
                         
                         is_next_to_water = False
                         for dx, dz in [(1,0), (-1,0), (0,1), (0,-1)]:
                             neighbor_h = calculate_surface_y(x + dx, z + dz, island)
                             if neighbor_h < island.water_level:
                                 is_next_to_water = True
                                 break
                        
                         if is_next_to_water and random.random() < 0.05:
                             place_sugarcane(mc_world, x, top_y, z)

                    # C. Trees, Cacti, Flowers, Dead Bushes
                    else:
                        tree_chance = 0.005 
                        if 'forest' in island.biome: tree_chance = 0.02
                        elif 'jungle' in island.biome: tree_chance = 0.05
                        elif 'desert' in island.biome: tree_chance = 0.01 
                        
                        if random.random() < tree_chance:
                            if island.biome == 'minecraft:desert':
                                if surface_block == 'minecraft:sand':
                                    place_cactus(mc_world, x, top_y, z)
                            else:
                                if surface_block == 'minecraft:grass_block':
                                    place_tree(mc_world, x, top_y + 1, z, island.biome)
                        
                        # D. Ground Cover
                        else:
                            # 1. DESERT -> Dead Bush
                            if island.biome == 'minecraft:desert' and surface_block == 'minecraft:sand':
                                if random.random() < 0.015:  # Reduced to 1.5%
                                    mc_world.set_block((x, top_y + 1, z), 'minecraft:dead_bush')
                            
                            # 2. GRASSY BIOMES -> Grass or Flower
                            elif surface_block == 'minecraft:grass_block':
                                
                                # Chance for ANY ground cover (grass or flower) reduced to 5%
                                if random.random() < 0.05: 
                                    
                                    # Inside that 5%, only 10% chance for a flower
                                    if random.random() < 0.10:
                                        flower_type = get_random_flower(island.biome)
                                        
                                        if flower_type in ['minecraft:rose_bush', 'minecraft:lilac', 'minecraft:peony']:
                                            mc_world.set_block((x, top_y + 1, z), flower_type + '[half=lower]')
                                            mc_world.set_block((x, top_y + 2, z), flower_type + '[half=upper]')
                                        else:
                                            mc_world.set_block((x, top_y + 1, z), flower_type)
                                    else:
                                        # 90% chance it's just grass/fern
                                        vegetation_type = 'minecraft:grass'
                                        if 'taiga' in island.biome:
                                            vegetation_type = 'minecraft:fern'
                                        mc_world.set_block((x, top_y + 1, z), vegetation_type)

                if x == 0 and z == 0:
                    spawn_y = max(top_y, island.water_level) + 2
                    
    return spawn_y

def main():
    mc_world = MinecraftWorld(world_name="Detailed Flora Floating Islands")
    
    volcanic_biome = create_volcanic_biome()
    mc_world.add_biome(volcanic_biome)
    print(f"Registered custom biome: {volcanic_biome.full_name}")

    biome_liquids = {biome: 'minecraft:water' for biome in STANDARD_BIOMES}
    biome_liquids[volcanic_biome.full_name] = 'minecraft:lava'
    
    island_layout = generate_island_layout(biome_liquid_map=biome_liquids, spawn_r_override=256)
    spawn_y = generate_islands(mc_world, island_layout)

    mc_world.set_spawn((0, spawn_y, 0))
    print("Exporting world...")
    mc_world.export('detailed_flora_floating_islands')
    print("Done!")

if __name__ == "__main__":
    main()