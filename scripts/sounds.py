import pygame

def load_sounds():
    shoot_sound = pygame.mixer.Sound("sounds/shoot.wav")
    explosion_sound = pygame.mixer.Sound("sounds/explosion.wav")
    powerup_sound = pygame.mixer.Sound("sounds/powerup.wav")
    pygame.mixer.music.load("sounds/background.mp3")
    pygame.mixer.music.play(-1)
    return shoot_sound, explosion_sound, powerup_sound
