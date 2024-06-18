import pygame
import random
from scripts.sprites import Enemy, PowerUp
from scripts.settings import WIDTH, HEIGHT

def check_collisions(player, enemies, bullets, powerups, all_sprites, score):
    hits = pygame.sprite.groupcollide(enemies, bullets, True, True)
    for hit in hits:
        score += 10
        explosion_sound.play()
        enemy = Enemy()
        all_sprites.add(enemy)
        enemies.add(enemy)
        if random.random() > 0.9:
            powerup = PowerUp(hit.rect.center)
            all_sprites.add(powerup)
            powerups.add(powerup)

    hits = pygame.sprite.spritecollide(player, enemies, False)
    for hit in hits:
        player.health -= 10
        explosion_sound.play()
        if player.health <= 0:
            player.kill()

    hits = pygame.sprite.spritecollide(player, powerups, True)
    for hit in hits:
        powerup_sound.play()
        player.health += 20
        if player.health > 100:
            player.health = 100

def draw_text(surf, text, size, x, y):
    font = pygame.font.Font(None, size)
    text_surface = font.render(text, True, WHITE)
    text_rect = text_surface.get_rect()
    text_rect.midtop = (x, y)
    surf.blit(text_surface, text_rect)

def spawn_enemies(level, enemies, all_sprites):
    for i in range(level * 5):
        enemy = Enemy()
        all_sprites.add(enemy)
        enemies.add(enemy)

def spawn_boss(all_sprites, enemies):
    boss = Boss()
    all_sprites.add(boss)
    enemies.add(boss)

def save_high_score(score):
    with open("high_scores.txt", "a") as file:
        file.write(f"{score}\n")

def load_high_scores():
    try:
        with open("high_scores.txt", "r") as file:
            return [int(line.strip()) for line in file.readlines()]
    except FileNotFoundError:
        return []

def draw_high_scores(screen, high_scores):
    high_scores = sorted(high_scores, reverse=True)[:5]
    for i, score in enumerate(high_scores):
        draw_text(screen, f"{i + 1}. {score}", 24, WIDTH // 2, 150 + i * 30)
