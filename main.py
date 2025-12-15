from minecraft import MinecraftWorld, MINECRAFT_DIFFICULTY_HARD, MINECRAFT_GAME_MODE_CREATIVE, CustomBiome, IntColor

def main():
    mc_world = MinecraftWorld(world_name="My Minecraft World")

    mc_world.set_block((0, -10, 0), 'minecraft:bedrock')

    mc_world.fill_blocks((-100, 0, -100), (100, 5, 100), 'minecraft:dirt')
    mc_world.fill_blocks((-100, 6, -100), (100, 6, 100), 'minecraft:grass_block')
    mc_world.fill_blocks((-100, 7, -100), (100, 7, 100), 'minecraft:grass')
    mc_world.fill_blocks((-10, 4, -10), (10, 6, 10), 'minecraft:water')
    mc_world.fill_blocks((-10, 7, -10), (10, 7, 10), 'minecraft:air')

    volcanic_biome = CustomBiome('volcanic_biome')
    volcanic_biome.set_colors(
        sky=IntColor.from_hex("#111111"),
        water=IntColor.from_hex("#D6D6D6"),
        fog=IntColor.from_hex("#111111"),
        water_fog=IntColor.from_hex("#FFFFFF"),
        grass=IntColor.from_hex("#363636")
    )

    volcanic_biome.set_particles("minecraft:white_ash", probability=0.1)

    mc_world.add_biome(volcanic_biome)
    
    mc_world.fill_biomes((0, 0, 0), (100, 255, 100), volcanic_biome.full_name)

    mc_world.fill_biomes((-100, 0, -100), (0, 255, 0), 'minecraft:desert')
    mc_world.fill_biomes((-100, 0, 0), (0, 255, 100), 'minecraft:taiga')

    mc_world.set_spawn((0, 8, 0))

    mc_world.set_difficulty(MINECRAFT_DIFFICULTY_HARD)
    mc_world.set_gamemode(MINECRAFT_GAME_MODE_CREATIVE)

    mc_world.export(folder_path='new_world')


if __name__ == "__main__":
    main()
