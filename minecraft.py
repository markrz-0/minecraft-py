import io
import zlib
import time
import random
import os
import numpy as np
import json
import nbtlib
from nbtlib import Compound, String, List, LongArray, Int, Long, Byte, Double, Float

# --- CONSTANTS ---
MINECRAFT_GAME_MODE_SURVIVAL = 0
MINECRAFT_GAME_MODE_CREATIVE = 1
MINECRAFT_GAME_MODE_ADVENTURE = 2
MINECRAFT_GAME_MODE_SPECTATOR = 3

MINECRAFT_DIFFICULTY_PEACEFUL = 0
MINECRAFT_DIFFICULTY_EASY = 1
MINECRAFT_DIFFICULTY_NORMAL = 2
MINECRAFT_DIFFICULTY_HARD = 3


def pack_integers(indices, palette_size, min_bits=1):
    """
    Generic bit-packer for Minecraft 1.16+
    indices: Flat list of integers (0, 1, 0, 2...)
    palette_size: How many items in the palette.
    min_bits: Minimum bits per entry (Blocks=4, Biomes=1).
    """
    # 1. Calculate bits required per entry
    required_bits = (palette_size - 1).bit_length()
    bits_per_entry = max(min_bits, required_bits)
    
    # 2. How many entries fit in a 64-bit integer?
    entries_per_long = 64 // bits_per_entry
    
    longs = []
    current_long = 0
    current_bit = 0
    count = 0
    
    for index in indices:
        # Shift the index to the current position and Add (OR) it to the Long
        current_long |= (int(index) << current_bit)
        
        current_bit += bits_per_entry
        count += 1
        
        # If the Long is full, save it and start a new one
        if count >= entries_per_long:
            # Handle Java's Signed 64-bit Integer (Two's Complement)
            if current_long >= (1 << 63): 
                current_long -= (1 << 64)
            
            longs.append(current_long)
            current_long = 0
            current_bit = 0
            count = 0
            
    # Save any remaining data
    if count > 0:
        if current_long >= (1 << 63): 
            current_long -= (1 << 64)
        longs.append(current_long)
        
    return longs

class Section:
    def __init__(self, y_index):
        self.y_index = y_index
        
        # --- BLOCKS (Y, Z, X) ---
        self.block_map = {"minecraft:air": 0} 
        self.block_palette = ["minecraft:air"]
        self.blocks = np.zeros((16, 16, 16), dtype=int)

        # --- BIOMES (Y, Z, X) - 4x4x4 Resolution ---
        self.biome_map = {"minecraft:plains": 0}
        self.biome_palette = ["minecraft:plains"]
        self.biomes = np.zeros((4, 4, 4), dtype=int)

    # --- BLOCK LOGIC ---
    def ensure_block_id(self, block_name):
        if block_name not in self.block_map:
            new_id = len(self.block_palette)
            self.block_map[block_name] = new_id
            self.block_palette.append(block_name)
        return self.block_map[block_name]

    def set_block(self, x, y, z, block_name):
        # Minecraft stores internal arrays as [Y, Z, X]
        self.blocks[y, z, x] = self.ensure_block_id(block_name)

    def fill_area(self, x1, y1, z1, x2, y2, z2, block_name):
        block_id = self.ensure_block_id(block_name)
        self.blocks[y1:y2, z1:z2, x1:x2] = block_id

    # --- BIOME LOGIC ---
    def ensure_biome_id(self, biome_name):
        if biome_name not in self.biome_map:
            new_id = len(self.biome_palette)
            self.biome_map[biome_name] = new_id
            self.biome_palette.append(biome_name)
        return self.biome_map[biome_name]

    def fill_biomes(self, x1, y1, z1, x2, y2, z2, biome_name):
        b_id = self.ensure_biome_id(biome_name)
        # Convert block coords (0-16) to quartile coords (0-4)
        bx1, by1, bz1 = x1 // 4, y1 // 4, z1 // 4
        bx2, by2, bz2 = (x2 + 3) // 4, (y2 + 3) // 4, (z2 + 3) // 4
        # Clamp to max 4
        bx2, by2, bz2 = min(4, bx2), min(4, by2), min(4, bz2)
        self.biomes[by1:by2, bz1:bz2, bx1:bx2] = b_id

    # --- EXPORT ---
    def to_nbt(self):
        # 1. Blocks
        block_palette_nbt = List[Compound]([Compound({'Name': String(n)}) for n in self.block_palette])
        block_states = Compound({'palette': block_palette_nbt})
        
        # FIX: Force min_bits=4 for Blocks
        if len(self.block_palette) > 1:
            packed = pack_integers(self.blocks.flatten(), len(self.block_palette), min_bits=4)
            block_states['data'] = LongArray(packed)

        # 2. Biomes
        biome_palette_nbt = List[String]([String(n) for n in self.biome_palette])
        biomes_tag = Compound({'palette': biome_palette_nbt})
        
        # Biomes use min_bits=1
        if len(self.biome_palette) > 1:
            packed_biomes = pack_integers(self.biomes.flatten(), len(self.biome_palette), min_bits=1)
            biomes_tag['data'] = LongArray(packed_biomes)

        return Compound({
            'Y': nbtlib.Byte(self.y_index),
            'block_states': block_states,
            'biomes': biomes_tag 
        })

class Chunk:
    def __init__(self, x, z):
        self.x = x
        self.z = z
        self.sections = {} 

    def get_section(self, y_index):
        if y_index not in self.sections:
            self.sections[y_index] = Section(y_index)
        return self.sections[y_index]

    def set_block(self, rel_x, y, rel_z, block_name):
        section = self.get_section(y // 16)
        section.set_block(rel_x, y % 16, rel_z, block_name)

    def fill_volume(self, rel_x1, y1, rel_z1, rel_x2, y2, rel_z2, block_name):
        start_sec = y1 // 16
        end_sec = (y2 - 1) // 16
        for sec_y in range(start_sec, end_sec + 1):
            section = self.get_section(sec_y)
            sec_base_y = sec_y * 16
            local_y1 = max(0, y1 - sec_base_y)
            local_y2 = min(16, y2 - sec_base_y)
            section.fill_area(rel_x1, local_y1, rel_z1, rel_x2, local_y2, rel_z2, block_name)

    def fill_biome_volume(self, rel_x1, y1, rel_z1, rel_x2, y2, rel_z2, biome_name):
        start_sec = y1 // 16
        end_sec = (y2 - 1) // 16
        for sec_y in range(start_sec, end_sec + 1):
            section = self.get_section(sec_y)
            sec_base_y = sec_y * 16
            local_y1 = max(0, y1 - sec_base_y)
            local_y2 = min(16, y2 - sec_base_y)
            section.fill_biomes(rel_x1, local_y1, rel_z1, rel_x2, local_y2, rel_z2, biome_name)

    def to_nbt(self):
        sections_nbt = List[Compound]()
        for s in self.sections.values():
            sections_nbt.append(s.to_nbt())

        dummy_heightmap = LongArray([0] * 37)

        return Compound({
            'DataVersion': nbtlib.Int(3465), 
            'xPos': nbtlib.Int(self.x),
            'zPos': nbtlib.Int(self.z),
            'yPos': nbtlib.Int(-64), 
            'sections': sections_nbt,
            'Status': String('minecraft:full'),
            'Heightmaps': Compound({
                'MOTION_BLOCKING': dummy_heightmap,
                'WORLD_SURFACE': dummy_heightmap
            })
        })

class Region:
    def __init__(self, r_x, r_z):
        self.r_x = r_x
        self.r_z = r_z
        self.chunks = {} 

    def get_chunk(self, x, z):
        if (x, z) not in self.chunks:
            self.chunks[(x, z)] = Chunk(x, z)
        return self.chunks[(x, z)]

    def save(self, filename):
        with open(filename, 'wb') as f:
            locations = bytearray(4096)
            timestamps = bytearray(4096)
            chunk_buffer = io.BytesIO()
            current_offset_sectors = 2 

            for (cx, cz), chunk in self.chunks.items():
                rx, rz = cx % 32, cz % 32
                header_index = 4 * (rx + rz * 32)

                nbt_file = nbtlib.File(chunk.to_nbt())
                temp_stream = io.BytesIO()
                nbt_file.write(temp_stream) # Raw bytes
                raw_data = temp_stream.getvalue()
                compressed_data = zlib.compress(raw_data)
                
                length = len(compressed_data) + 1
                chunk_buffer.write(length.to_bytes(4, 'big'))
                chunk_buffer.write(b'\x02') # Zlib
                chunk_buffer.write(compressed_data)

                # Padding
                total_size = 4 + 1 + len(compressed_data)
                padding = 4096 - (total_size % 4096)
                if padding < 4096:
                    chunk_buffer.write(b'\x00' * padding)
                else:
                    padding = 0

                sectors_used = (total_size + padding) // 4096
                
                loc_value = (current_offset_sectors << 8) | (sectors_used & 0xFF)
                locations[header_index : header_index+4] = loc_value.to_bytes(4, 'big')
                current_offset_sectors += sectors_used

            f.write(locations)
            f.write(timestamps)
            f.write(chunk_buffer.getvalue())

class MinecraftWorldSimple:
    def __init__(self, world_name="Generated World"):
        self.regions = {} 
        self.world_name = world_name
        self.spawn_coords = (0, 60, 0)
        self.difficulty = MINECRAFT_DIFFICULTY_NORMAL
        self.gamemode = MINECRAFT_GAME_MODE_CREATIVE
        self.hardcode = False


    def set_block(self, pos, block_name):
        x, y, z = pos
        cx, cz = x // 16, z // 16
        rx, rz = cx // 32, cz // 32
        
        if (rx, rz) not in self.regions: self.regions[(rx, rz)] = Region(rx, rz)
        chunk = self.regions[(rx, rz)].get_chunk(cx, cz)
        chunk.set_block(x % 16, y, z % 16, block_name)

    def fill_blocks(self, start, end, block_name):
        x1, y1, z1 = start
        x2, y2, z2 = end
        sx, ex = min(x1, x2), max(x1, x2) + 1
        sy, ey = min(y1, y2), max(y1, y2) + 1
        sz, ez = min(z1, z2), max(z1, z2) + 1

        min_cx, max_cx = sx // 16, (ex - 1) // 16
        min_cz, max_cz = sz // 16, (ez - 1) // 16

        for cx in range(min_cx, max_cx + 1):
            for cz in range(min_cz, max_cz + 1):
                rx, rz = cx // 32, cz // 32
                if (rx, rz) not in self.regions: self.regions[(rx, rz)] = Region(rx, rz)
                chunk = self.regions[(rx, rz)].get_chunk(cx, cz)
                
                cbx, cbz = cx * 16, cz * 16
                chunk.fill_volume(
                    max(0, sx - cbx), sy, max(0, sz - cbz),
                    min(16, ex - cbx), ey, min(16, ez - cbz),
                    block_name
                )

    def fill_biomes(self, start, end, biome_name):
        x1, y1, z1 = start
        x2, y2, z2 = end
        sx, ex = min(x1, x2), max(x1, x2) + 1
        sy, ey = min(y1, y2), max(y1, y2) + 1
        sz, ez = min(z1, z2), max(z1, z2) + 1

        min_cx, max_cx = sx // 16, (ex - 1) // 16
        min_cz, max_cz = sz // 16, (ez - 1) // 16

        for cx in range(min_cx, max_cx + 1):
            for cz in range(min_cz, max_cz + 1):
                rx, rz = cx // 32, cz // 32
                if (rx, rz) not in self.regions: self.regions[(rx, rz)] = Region(rx, rz)
                chunk = self.regions[(rx, rz)].get_chunk(cx, cz)
                
                cbx, cbz = cx * 16, cz * 16
                chunk.fill_biome_volume(
                    max(0, sx - cbx), sy, max(0, sz - cbz),
                    min(16, ex - cbx), ey, min(16, ez - cbz),
                    biome_name
                )

    def export(self, folder_path):
        if not os.path.exists(folder_path): os.makedirs(folder_path)
        region_folder = os.path.join(folder_path, 'region')
        if not os.path.exists(region_folder): os.makedirs(region_folder)

        print(f"Exporting level.dat...")
        level_dat = self._create_level_dat()
        level_dat.save(os.path.join(folder_path, "level.dat"), gzipped=True)

        for (rx, rz), region in self.regions.items():
            print(f"Exporting Region {rx}.{rz}...")
            region.save(os.path.join(region_folder, f"r.{rx}.{rz}.mca"))
        
        print("Done!")

    def set_spawn(self, spawn_coords):
        self.spawn_coords = spawn_coords

    def set_difficulty(self, difficulty: int):
        self.difficulty = difficulty
    
    def set_gamemode(self, gamemode: int):
        self.gamemode = gamemode

    def set_hardcore(self, hardcore: bool):
        self.hardcode = hardcore

    def _create_level_dat(self):
        seed = random.getrandbits(32)
        now = int(time.time() * 1000)
        
        # Generator: Void World (Air only)
        world_gen_settings = Compound({
            "seed": Long(seed),
            "generate_features": Byte(0),
            "bonus_chest": Byte(0),
            "dimensions": Compound({
                "minecraft:overworld": Compound({
                    "type": String("minecraft:overworld"),
                    "generator": Compound({
                        "type": String("minecraft:flat"),
                        "settings": Compound({
                            "layers": List[Compound]([
                                Compound({"block": String("minecraft:air"), "height": Int(1)})
                            ]),
                            "biome": String("minecraft:the_void"),
                        })
                    })
                })
            })
        })

        sx, sy, sz = self.spawn_coords

        data = Compound({
            "Data": Compound({
                "allowCommands": Byte(1),
                "GameType": Int(self.gamemode),
                "Difficulty": Byte(self.difficulty),
                "hardcore": Byte(int(self.hardcode)),
                "LevelName": String(self.world_name),
                "version": Int(19133),
                "DataVersion": Int(3465), 
                "WorldGenSettings": world_gen_settings,
                "SpawnX": Int(sx), "SpawnY": Int(sy), "SpawnZ": Int(sz),
                
                # Standard Spawn Info
                "SpawnX": Int(sx),
                "SpawnY": Int(sy),
                "SpawnZ": Int(sz),

                # 2. PLAYER STATE (For First Join)
                # This forces the player to exist at this specific location
                "Player": Compound({
                    # Pos: [X, Y, Z] (Must be Doubles)
                    "Pos": List[Double]([Double(sx + 0.5), Double(sy), Double(sz + 0.5)]),
                    # Rotation: [Yaw, Pitch] (Must be Floats)
                    "Rotation": List[Float]([Float(0.0), Float(0.0)]),
                    # Motion: [dX, dY, dZ]
                    "Motion": List[Double]([Double(0), Double(0), Double(0)]),
                    "OnGround": Byte(1),
                    
                    # Optional: Set abilities so you are flying immediately
                    "abilities": Compound({
                        "flying": Byte(1),
                        "mayfly": Byte(1),
                        "instabuild": Byte(1)
                    })
                }),
                
                "Time": Long(0),
                "DayTime": Long(0),
                "LastPlayed": Long(now),
                "initialized": Byte(1), # Tells game "we have set this up already"
                
                "raining": Byte(0),
                "thundering": Byte(0),
                "warned_old_generation": Byte(1) # Suppresses "World from old version" warning
            })
        })
        return nbtlib.File(data)


class IntColor:
    @classmethod
    def from_hex(cls, color: str):
        return int(color.replace('#', ''), 16)


class CustomBiome:
    def __init__(self, name, namespace="custom"):
        self.name = name
        self.namespace = namespace
        self.full_name = f"{namespace}:{name}"
        
        # Default Properties (Standard Plains-like)
        self.properties = {
            "has_precipitation": True,
            "temperature": 0.8,
            "downfall": 0.4,
            "effects": {
                "sky_color": IntColor.from_hex('#78A7FF'), 
                "fog_color": IntColor.from_hex('#C0D8FF'),
                "water_color": IntColor.from_hex('#3F76E4'),
                "water_fog_color": IntColor.from_hex('#050533'),
                "grass_color_modifier": "none",
            }
        }

        self.spawners = {
            "monster": [],
            "creature": [],
            "ambient": [],
            "water_creature": [],
            "underground_water_creature": [],
            "water_ambient": [],
            "misc": [],
            "axolotls": []
        }

        # Spawn Costs: Pathfinding budget for mobs (Empty = Default)
        self.spawn_costs = {}
        
        # Carvers: Caves and Ravines (Empty = Solid ground)
        self.carvers = {
            "air": [],
            "liquid": []
        }

        self.features = [[], [], [], [], [], [], [], [], [], [], []]

    def set_colors(self, sky=None, water=None, fog=None, water_fog=None, foliage=None, grass=None):
        """
        Colors must be Integers (Decimal). 
        Hex users: use IntColor.from_hex('#ff0000')
        """
        if sky: self.properties["effects"]["sky_color"] = sky
        if water: self.properties["effects"]["water_color"] = water
        if fog: self.properties["effects"]["fog_color"] = fog
        if water_fog: self.properties["effects"]["water_fog_color"] = water_fog
        
        # Foliage/Grass overrides are optional. If not set, they depend on temperature.
        if foliage: self.properties["effects"]["foliage_color"] = foliage
        if grass: self.properties["effects"]["grass_color"] = grass

    def add_mob_spawn(self, category, entity_name, weight=10, min_count=1, max_count=4):
        """
        category: "monster", "creature", "water_creature", etc.
        entity_name: "minecraft:zombie", "minecraft:cow"
        weight: Chance to spawn (100 = very common, 1 = rare)
        """
        if category not in self.spawners:
            print(f"Warning: Category '{category}' is not valid. Using 'misc'.")
            category = "misc"

        self.spawners[category].append({
            "type": entity_name,
            "weight": weight,
            "minCount": min_count,
            "maxCount": max_count
        })

    def set_particles(self, particle_name, probability=0.01):
        """
        Example: particle_name = "minecraft:ash"
        """
        self.properties["effects"]["particle"] = {
            "options": {"type": particle_name},
            "probability": probability
        }

    def set_temperature(self, temperature: float):
        self.properties['temperature'] = temperature
        
    def to_dict(self):
        return {
            "has_precipitation": self.properties["has_precipitation"],
            "temperature": self.properties["temperature"],
            "downfall": self.properties["downfall"],
            "temperature_modifier": "none",
            "effects": self.properties["effects"],

            "spawners": self.spawners,
            "spawn_costs": self.spawn_costs,
            "carvers": self.carvers,
            "features": self.features
        }


class MinecraftWorld(MinecraftWorldSimple):
    def __init__(self, world_name="Generated World"):
        super().__init__(world_name)
        self.custom_biomes = []

    def add_biome(self, biome: CustomBiome):
        self.custom_biomes.append(biome)
        return biome

    def export(self, folder_path):
        # 1. Export the standard Chunk/Level data
        super().export(folder_path)
        
        # 2. Generate the Datapack
        self._export_datapack(folder_path)

    def _export_datapack(self, folder_path):
        print("Generating Datapack for custom biomes...")
        
        pack_name = "generated_biomes"
        # Path: World/datapacks/generated_biomes
        base_path = os.path.join(folder_path, "datapacks", pack_name)
        
        # 1. Create pack.mcmeta (Required)
        os.makedirs(base_path, exist_ok=True)
        with open(os.path.join(base_path, "pack.mcmeta"), "w") as f:
            json.dump({
                "pack": {
                    "pack_format": 15, # 1.20 format
                    "description": "Custom biomes generated by Python"
                }
            }, f, indent=4)

        # 2. Write Biome JSONs
        for biome in self.custom_biomes:
            # Path: data/<namespace>/worldgen/biome/<name>.json
            biome_path = os.path.join(base_path, "data", biome.namespace, "worldgen", "biome")
            os.makedirs(biome_path, exist_ok=True)
            
            with open(os.path.join(biome_path, f"{biome.name}.json"), "w") as f:
                json.dump(biome.to_dict(), f, indent=4)