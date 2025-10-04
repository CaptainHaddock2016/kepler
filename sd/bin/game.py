import random

def main(argv, cwd):
    print("Welcome to Guess the Number!")
    print("I'm thinking of a number between 1 and 20.")
    number = random.randint(1, 20)
    tries = 0

    while True:
        guess = input("Take a guess: ")
        tries += 1

        if not guess.isdigit():
            print("Please enter a number!")
            continue

        guess = int(guess)
        if guess < number:
            print("Too low!")
        elif guess > number:
            print("Too high!")
        else:
            print(f"You got it in {tries} tries!")
            break

