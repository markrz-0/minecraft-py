import random
import math
from dataclasses import dataclass
from noise import pnoise2, snoise3
from minecraft import MinecraftWorld, CustomBiome, IntColor

# --- Configuration ---
NUM_ISLANDS = 1000
ISLAND_RADIUS_MIN = 16
ISLAND_RADIUS_MAX = 100
ISLAND_Y_LEVEL = 60
ISLAND_SPREAD = 1000

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

# --- Ore Configuration ---
# Global chance for a stone/deepslate block to become an ore (0.05 = 5%)
ORE_DENSITY = 0.05 

# Dictionary of {Biome Keyword: {Ore Name: Weight}}
# If a biome name matches the keyword, it uses that specific list.
# 'default' is used if no other match is found.
BIOME_ORES = {
    'default': {
        'minecraft:coal_ore': 40,
        'minecraft:copper_ore': 30,
        'minecraft:iron_ore': 20,
        'minecraft:gold_ore': 10,
        'minecraft:redstone_ore': 8,
        'minecraft:lapis_ore': 5,
        'minecraft:diamond_ore': 2,
        'minecraft:emerald_ore': 1
    },
    'badlands': {
        'minecraft:gold_ore': 50,  # Significantly more gold
        'minecraft:coal_ore': 20,
        'minecraft:iron_ore': 20,
        'minecraft:copper_ore': 15,
        'minecraft:diamond_ore': 2
    },
    'volcanic': {
        'minecraft:coal_ore': 30,
        'minecraft:gold_ore': 25
    },
    'snowy': {
        'minecraft:coal_ore': 40,
        'minecraft:iron_ore': 20,
        'minecraft:emerald_ore': 5, # More emeralds in mountains/snow
        'minecraft:lapis_ore': 5,
        'minecraft:diamond_ore': 2
    }
}

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
    'dark_forest': ['minecraft:rose_bush', 'minecraft:peony', 'minecraft:lily_of_the_valley', 'minecraft:brown_mushroom', 'minecraft:red_mushroom'],
    'cherry': ['minecraft:pink_petals'],
    'taiga': ['minecraft:fern'],
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

# --- Ore Logic ---

def determine_ore(biome_name, host_block):
    """
    Decides if a block should become an ore based on biome weights.
    Returns the new block string, or the original host_block if no ore is generated.
    """
    # 1. Global Density Check
    if random.random() > ORE_DENSITY:
        return host_block

    # 2. Find correct dictionary for this biome
    ore_weights = BIOME_ORES['default']
    for key, val in BIOME_ORES.items():
        if key in biome_name:
            ore_weights = val
            break
            
    # 3. Weighted Random Choice
    ores = list(ore_weights.keys())
    weights = list(ore_weights.values())
    chosen_ore = random.choices(ores, weights=weights, k=1)[0]
    
    # 4. Deepslate Conversion
    # If the surrounding rock is deepslate, try to use the deepslate version of the ore
    if host_block == 'minecraft:deepslate':
        # List of ores that actually have deepslate variants in Vanilla
        has_deepslate_variant = [
            'minecraft:coal_ore', 'minecraft:iron_ore', 'minecraft:gold_ore', 
            'minecraft:copper_ore', 'minecraft:redstone_ore', 
            'minecraft:lapis_ore', 'minecraft:diamond_ore', 'minecraft:emerald_ore'
        ]
        if chosen_ore in has_deepslate_variant:
            return chosen_ore.replace("minecraft:", "minecraft:deepslate_")
            
    return chosen_ore

# --- Vegetation Logic ---

def place_tree(mc_world, x, y, z, biome_name):
    # 1. Defaults
    log = 'minecraft:oak_log'
    leaves = 'minecraft:oak_leaves'
    shape = 'standard'
    
    # 2. Assign Type based on Biome
    if 'spruce' in biome_name or 'taiga' in biome_name or 'snowy' in biome_name:
        log = 'minecraft:spruce_log'
        leaves = 'minecraft:spruce_leaves'
        shape = 'pine'
    elif 'birch' in biome_name or ('minecraft:forest' == biome_name and random.random() < 0.5):
        log = 'minecraft:birch_log'
        leaves = 'minecraft:birch_leaves'
        shape = 'standard' 
    elif 'jungle' in biome_name:
        log = 'minecraft:jungle_log'
        leaves = 'minecraft:jungle_leaves'
        shape = 'tall' 
    elif 'acacia' in biome_name or 'savanna' in biome_name:
        log = 'minecraft:acacia_log'
        leaves = 'minecraft:acacia_leaves'
        shape = 'acacia'
    elif 'dark_forest' in biome_name:
        log = 'minecraft:dark_oak_log'
        leaves = 'minecraft:dark_oak_leaves'
        shape = 'thick' 
    elif 'cherry' in biome_name:
        log = 'minecraft:cherry_log'
        leaves = 'minecraft:cherry_leaves'
        shape = 'standard'
    elif 'swamp' in biome_name:
        log = 'minecraft:oak_log'
        leaves = 'minecraft:oak_leaves'
        shape = 'standard' 

    leaves = f"{leaves}[persistent=true]"

    # --- 3a. Vine Helper ---
    def try_spawn_vine_column(src_x, src_y, src_z):
        if 'jungle' not in biome_name and 'swamp' not in biome_name:
            return

        chance = 0.15 if 'jungle' in biome_name else 0.10
        min_len = 3
        max_len = 8 if 'jungle' in biome_name else 5

        # Neighbors: (dx, dz, prop_string)
        neighbors = [
            (0, -1, "south=true"), 
            (0, 1, "north=true"),  
            (-1, 0, "east=true"),  
            (1, 0, "west=true")    
        ]

        for dx, dz, prop in neighbors:
            target_x = src_x + dx
            target_z = src_z + dz
            
            if mc_world.get_block((target_x, src_y, target_z)) == 'minecraft:air':
                if random.random() < chance:
                    length = random.randint(min_len, max_len)
                    for i in range(length):
                        vy = src_y - i
                        if i > 0:
                            current = mc_world.get_block((target_x, vy, target_z))
                            if current != 'minecraft:air': break
                        mc_world.set_block((target_x, vy, target_z), f"minecraft:vine[{prop}]")

    # --- 3b. Cocoa Helper ---
    def try_spawn_cocoa(src_x, src_y, src_z):
        """
        Spawns cocoa pods on the sides of jungle logs.
        The 'facing' property must point TOWARDS the log.
        """
        if 'jungle' not in biome_name:
            return
            
        # Chance to spawn a pod on this log block
        if random.random() > 0.15: # 15% chance per log block to attempt spawning
            return

        # Neighbors: (dx, dz, facing_dir)
        # If the pod is at (x+1), it is EAST of the log, so it must FACE WEST to touch the log.
        neighbors = [
            (0, -1, "south"), # Pod is North (z-1), faces South to touch log
            (0, 1, "north"),  # Pod is South (z+1), faces North to touch log
            (-1, 0, "east"),  # Pod is West (x-1), faces East to touch log
            (1, 0, "west")    # Pod is East (x+1), faces West to touch log
        ]
        
        # Pick one random side to try (don't cover the whole tree in pods)
        dx, dz, facing = random.choice(neighbors)
        target_x = src_x + dx
        target_z = src_z + dz
        
        if mc_world.get_block((target_x, src_y, target_z)) == 'minecraft:air':
            age = random.randint(0, 2)
            mc_world.set_block((target_x, src_y, target_z), f"minecraft:cocoa[facing={facing},age={age}]")


    # 4. Generate Shape
    if shape == 'standard':
        height = random.randint(5, 7)
        if 'birch' in biome_name: height += 2 
        
        # Trunk
        for i in range(height):
            mc_world.set_block((x, y + i, z), log)
            if 'jungle' in biome_name:
                try_spawn_vine_column(x, y + i, z)
                try_spawn_cocoa(x, y + i, z) # Cocoa check

        leaf_start = y + height - 2
        for ly in range(leaf_start, leaf_start + 4):
            radius = 2
            if ly == leaf_start + 3: radius = 1 
            for lx in range(x - radius, x + radius + 1):
                for lz in range(z - radius, z + radius + 1):
                    if lx == x and lz == z and ly < y + height: continue
                    d = math.sqrt((lx-x)**2 + (lz-z)**2)
                    if d <= radius + 0.5:
                         if random.random() > 0.15: 
                             mc_world.set_block((lx, ly, lz), leaves)
                             try_spawn_vine_column(lx, ly, lz)

    elif shape == 'pine':
        height = random.randint(7, 10)
        mc_world.fill_blocks((x, y, z), (x, y + height - 1, z), log)
        current_y = y + 3
        current_r = 3
        while current_y < y + height + 1:
            for lx in range(x - current_r, x + current_r + 1):
                for lz in range(z - current_r, z + current_r + 1):
                    if lx == x and lz == z and current_y < y + height: continue
                    if math.sqrt((lx-x)**2 + (lz-z)**2) <= current_r + 0.5:
                        mc_world.set_block((lx, current_y, lz), leaves)
                        try_spawn_vine_column(lx, current_y, lz)
            current_y += 1
            if current_r > 0: current_r -= 1
            else: current_r = 1 

    elif shape == 'thick':
        height = random.randint(6, 8)
        mc_world.fill_blocks((x, y, z), (x+1, y + height - 1, z+1), log)
        leaf_start = y + height - 2
        for ly in range(leaf_start, leaf_start + 3):
            radius = 4 if ly == leaf_start else 2
            for lx in range(x - radius, x + radius + 2):
                for lz in range(z - radius, z + radius + 2):
                    d = math.sqrt((lx - (x+0.5))**2 + (lz - (z+0.5))**2)
                    if d <= radius + 0.8:
                        mc_world.set_block((lx, ly, lz), leaves)
                        try_spawn_vine_column(lx, ly, lz)

    elif shape == 'acacia':
        height = random.randint(5, 6)
        mc_world.fill_blocks((x, y, z), (x, y + 2, z), log)
        for i in range(1, 4):
            mc_world.set_block((x + i, y + 2 + i, z), log)
            if i == 3:
                for lx in range(x+i - 2, x+i + 3):
                    for lz in range(z - 2, z + 3):
                        mc_world.set_block((lx, y+2+i, lz), leaves)
        for i in range(1, 3):
            mc_world.set_block((x - i, y + 2 + i, z), log)
            if i == 2:
                for lx in range(x-i - 2, x-i + 3):
                    for lz in range(z - 2, z + 3):
                        mc_world.set_block((lx, y+2+i, lz), leaves)

    elif shape == 'tall':
        height = random.randint(10, 14)
        # Trunk
        for i in range(height):
            mc_world.set_block((x, y + i, z), log)
            if 'jungle' in biome_name:
                try_spawn_vine_column(x, y + i, z)
                try_spawn_cocoa(x, y + i, z) # Cocoa check

        leaf_start = y + height - 3
        for ly in range(leaf_start, leaf_start + 4):
            radius = 3 if ly < leaf_start + 2 else 2
            for lx in range(x - radius, x + radius + 1):
                for lz in range(z - radius, z + radius + 1):
                    if lx == x and lz == z and ly < y + height: continue
                    if random.random() < 0.8:
                        mc_world.set_block((lx, ly, lz), leaves)
                        try_spawn_vine_column(lx, ly, lz)


def place_big_mushroom(mc_world, x, y, z, mushroom_type='red'):
    height = random.randint(5, 7)
    mc_world.fill_blocks((x, y, z), (x, y + height - 1, z), 'minecraft:mushroom_stem')
    cap_center_y = y + height
    
    if mushroom_type == 'red':
        block = 'minecraft:red_mushroom_block'
        radius = random.randint(3, 4)
        for dy in range(radius + 1):
            slice_radius = int(math.sqrt(radius**2 - dy**2))
            level_y = cap_center_y + dy - 1 
            for lx in range(x - slice_radius, x + slice_radius + 1):
                for lz in range(z - slice_radius, z + slice_radius + 1):
                    if math.sqrt((lx-x)**2 + (lz-z)**2) <= slice_radius + 0.5:
                         mc_world.set_block((lx, level_y, lz), block)
                         
    elif mushroom_type == 'brown':
        block = 'minecraft:brown_mushroom_block'
        radius = random.randint(3, 5)
        for lx in range(x - radius, x + radius + 1):
            for lz in range(z - radius, z + radius + 1):
                if math.sqrt((lx-x)**2 + (lz-z)**2) <= radius + 0.5:
                     mc_world.set_block((lx, cap_center_y, lz), block)

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
    volcanic.add_mob_spawn(
        category="monster", 
        entity_name="minecraft:witch", 
        weight=10,       # Higher = spawns more often compared to other mobs
        min_count=4,     # Minimum mobs per pack
        max_count=4      # Maximum mobs per pack
    )
    volcanic.add_mob_spawn(
        category="monster", 
        entity_name="minecraft:skeleton", 
        weight=20,       # Higher = spawns more often compared to other mobs
        min_count=4,     # Minimum mobs per pack
        max_count=4      # Maximum mobs per pack
    )
    return volcanic

def generate_island_layout(biome_liquid_map, spawn_r_override=None):
    print("Calculating island layout...")
    islands_layout = []
    available_biomes = list(biome_liquid_map.keys())

    spawn_r = spawn_r_override if spawn_r_override else random.randint(ISLAND_RADIUS_MIN, ISLAND_RADIUS_MAX)
    spawn_island = IslandData(
        x=0, z=0, radius=spawn_r, 
        biome='minecraft:forest', 
        has_lake=True, 
        water_level=ISLAND_Y_LEVEL - 2,
        liquid_block='minecraft:water'
    )
    islands_layout.append(spawn_island)
    
    attempts = 0
    cr = ISLAND_RADIUS_MAX
    while len(islands_layout) < NUM_ISLANDS and cr >= ISLAND_RADIUS_MIN:
        attempts += 1
        cx = random.randint(-ISLAND_SPREAD, ISLAND_SPREAD)
        cz = random.randint(-ISLAND_SPREAD, ISLAND_SPREAD)
        if attempts > 10000:
            cr -= 1
            attempts = 0
        
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
                    if cave_noise > CAVE_THRESHOLD and y <= island.water_level - 3 and 'volcanic_biome' not in island.biome:
                        continue 

                    depth = top_y - y
                    block_type = 'minecraft:stone' 

                    if depth == 0:
                        if y < island.water_level: block_type = 'minecraft:dirt' 
                        else: block_type = 'minecraft:grass_block'
                    elif depth < 5: block_type = 'minecraft:dirt'
                    elif depth < 15: block_type = 'minecraft:stone'
                    else: block_type = 'minecraft:deepslate'

                    # --- BIOME BLOCK SWAPS ---
                    
                    if island.biome == 'minecraft:desert':
                        if block_type == 'minecraft:grass_block': block_type = 'minecraft:sand'
                        elif block_type == 'minecraft:dirt': block_type = 'minecraft:sandstone'
                    elif island.biome == 'minecraft:badlands':
                        if block_type == 'minecraft:grass_block': block_type = 'minecraft:red_sand'
                        elif block_type == 'minecraft:dirt': block_type = 'minecraft:red_sandstone'
                        elif block_type == 'minecraft:stone': block_type = 'minecraft:terracotta'
                    elif 'volcanic_biome' in island.biome:
                        if block_type in ['minecraft:grass_block', 'minecraft:dirt'] and random.random() < 0.25:
                            block_type = 'minecraft:gravel'
                        elif block_type == 'minecraft:deepslate' and random.random() < 0.15:
                            block_type = 'minecraft:obsidian'
                        elif block_type in ['minecraft:stone', 'minecraft:deepslate'] and random.random() < 0.15:
                            # 1. Horizontal Safety: Keep lava away from the side edges
                            is_horizontal_safe = dist < (0.8 * island.radius)
                            
                            # 2. Vertical Safety: Keep lava away from the top surface and bottom void
                            # We ensure it is at least 3 blocks below the surface and 3 blocks above the bottom
                            is_vertical_safe = (y < top_y - 3) and (y > bottom_y + 3)

                            if is_horizontal_safe and is_vertical_safe:
                                block_type = 'minecraft:lava'
                            else:
                                # If it's too close to any edge, use Magma (solid/safe)
                                block_type = 'minecraft:magma_block'
 
                    # --- ORE GENERATION ---
                    # Only attempt ore placement in valid ground blocks
                    if block_type in ['minecraft:stone', 'minecraft:deepslate']:
                        block_type = determine_ore(island.biome, block_type)

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
                         surface_block in ['minecraft:grass_block', 'minecraft:sand', 'minecraft:dirt', 'minecraft:red_sand']:
                         
                         is_next_to_water = False
                         for dx, dz in [(1,0), (-1,0), (0,1), (0,-1)]:
                             neighbor_h = calculate_surface_y(x + dx, z + dz, island)
                             if neighbor_h < island.water_level:
                                 is_next_to_water = True
                                 break
                        
                         if is_next_to_water and random.random() < 0.05:
                             place_sugarcane(mc_world, x, top_y, z)

                    # C. Trees, Cacti, Mushrooms, Flowers, Dead Bushes
                    else:
                        tree_chance = 0.005 
                        if 'forest' in island.biome: tree_chance = 0.02
                        elif 'jungle' in island.biome: tree_chance = 0.05
                        elif 'desert' in island.biome or 'badlands' in island.biome: 
                            tree_chance = 0.01 
                        
                        if random.random() < tree_chance:
                            if island.biome == 'minecraft:desert' or island.biome == 'minecraft:badlands':
                                if surface_block in ['minecraft:sand', 'minecraft:red_sand']:
                                    place_cactus(mc_world, x, top_y, z)
                            else:
                                if surface_block == 'minecraft:grass_block':
                                    if 'dark_forest' in island.biome and random.random() < 0.25:
                                        m_type = random.choice(['red', 'brown'])
                                        place_big_mushroom(mc_world, x, top_y + 1, z, m_type)
                                    else:
                                        place_tree(mc_world, x, top_y + 1, z, island.biome)
                        
                        # D. Ground Cover
                        else:
                            # 1. DESERT & BADLANDS -> Dead Bush
                            if (island.biome == 'minecraft:desert' and surface_block == 'minecraft:sand') or \
                               (island.biome == 'minecraft:badlands' and surface_block == 'minecraft:red_sand'):
                                if random.random() < 0.015: 
                                    mc_world.set_block((x, top_y + 1, z), 'minecraft:dead_bush')
                            
                            # 2. GRASSY BIOMES
                            elif surface_block == 'minecraft:grass_block':
                                
                                placed_crop = False
                                
                                if 'taiga' in island.biome:
                                    if random.random() < 0.01:
                                        mc_world.set_block((x, top_y + 1, z), 'minecraft:pumpkin')
                                        placed_crop = True
                                    elif random.random() < 0.04:
                                        mc_world.set_block((x, top_y + 1, z), 'minecraft:sweet_berry_bush[age=2]')
                                        placed_crop = True
                                        
                                elif 'jungle' in island.biome:
                                    if random.random() < 0.01:
                                        mc_world.set_block((x, top_y + 1, z), 'minecraft:melon')
                                        placed_crop = True
                                        
                                if not placed_crop and random.random() < 0.05: 
                                    if random.random() < 0.10:
                                        flower_type = get_random_flower(island.biome)
                                        if flower_type in ['minecraft:rose_bush', 'minecraft:lilac', 'minecraft:peony']:
                                            mc_world.set_block((x, top_y + 1, z), flower_type + '[half=lower]')
                                            mc_world.set_block((x, top_y + 2, z), flower_type + '[half=upper]')
                                        else:
                                            mc_world.set_block((x, top_y + 1, z), flower_type)
                                    else:
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
    
    island_layout = generate_island_layout(biome_liquid_map=biome_liquids, spawn_r_override=128)
    spawn_y = generate_islands(mc_world, island_layout)

    mc_world.set_spawn((0, spawn_y, 0))
    print("Exporting world...")
    mc_world.export('detailed_flora_floating_islands')
    print("Done!")

if __name__ == "__main__":
    main()