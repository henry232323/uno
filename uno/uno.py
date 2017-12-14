"""
A quick explanation of the protocol:
Introduction:
    1. We have a set timeout to wait for players to connect.
    2. Players connect within that time under the max.
    3. If no players connect we raise
    4. The game shall start if we run out of time but still have players
The Client:
    1. The Client(s) will connect to the server using a commonly known address
    2. The Client will immediately send a name ending in a newline for identification
    3. Names shall not be excessively long. Numerically limited to 1024 chars.
    4. From then on, the Client only sends messages when asked by the server.
    5. Each message shall end with a newline to separate messages
    6. When the connection is closed that is indicative of a "game over"
        - That game over shall be preceded by a message declaring the winner
    7. The Client shall handle each of the following commands as specified
        a. "message" - The Client shall display messages of this type to the user
        b. "input" - The Client shall display this message while asking for an input from the user to be sent back to the server
        c. "error" - The Client has failed to send a name in time, and thus will be connected. Do not display game over.
The Server:
    1. The Server shall wait until we finish the connection and name stage before it sends any messages
    2. All messages sent shall be in a standard format as the following
        a. A JSON encoded message with NO indentation or spacing
        b. Newlines are used exclusively for separating messages
        c. Each message is a JSON dumped dictionary with one of three keys
            i. "message" - An informational message to be displayed by the Client.
            ii. "input" - The Server is asking for an input based off the message associated.
            iii. "error" - The Client has failed to send a name and has been disconnected.
"""

from random import shuffle, choice, randint
from collections import Counter

import socket
import select
import time
import json
import time


colors = ["RED", "BLUE", "GREEN", "YELLOW"]
cards = []

for color in colors: # Four "0" cards
    cards.append(('0', color))

_dc = colors * 2

for color in _dc: # 8 of each number 1-9
    for x in range(1, 10):
        cards.append((str(x), color))

for color in _dc:  # Four skip, reverse, and draw2 cards
    cards.append(("SKIP", color))
    cards.append(("REVERSE", color))
    cards.append(("DRAW2", color))

cards.extend((("WILD", "ALL"), ("WILD4", "ALL"))*4) # 4 wild cards and 4 wild + draw 4 cards

def generate_deck():
    """Generate a deck from the available cards"""
    deck = cards[::]
    shuffle(deck)
    return deck

def generate_hand(deck):
    """Generate a random hand from the available cards"""
    return [deck.pop() for x in range(7)]

def fcard(card):
    """Create format string for card display"""
    return f"{card[0]} {card[1]}"

def fhand(hand):
    """Create format string for hand display"""
    return ", ".join(fcard(card) for card in hand)

def draw_card(deck, played):
    """Draw a card, if deck is empty, fill with played cards"""
    if deck:
        return deck.pop()
    else:
        top = played.pop()
        shuffle(played)
        deck.extend(played)
        played.clear()
        played.append(top)
        return deck.pop()
        

def start(connected, n_ai_players):
    """Starts the game with the given number of ai players and a list of connected players"""
    if n_ai_players < 0 or n_ai_players != int(n_ai_players):
        raise ValueError("n_ai_players must be a positive integer!")
    if len(cards) // (n_ai_players + len(connected)) < 7:
        raise ValueError("Cannot start a game with too many players!")
    
    deck = generate_deck()  # Our deck
    played = []  # Cards that have been played
    ai_hands = [(f"Player {n}", generate_hand(deck)) for n in range(n_ai_players)]
    play_order = [(user, generate_hand(deck)) for user in connected.items()]
    play_order.extend(ai_hands)
    # An AI is just a (str_name, hand)
    # A player is a ((socket, player_name), hand)

    sc = deck.pop()  # Get our start card
    played.append(sc)
    broadcast(connected, f"Start Card: {fcard(sc)}")
    while True:
        skipped = False  
        for i, (player, hand) in enumerate(play_order):
            if skipped:
                skipped = False  # If the last person played a skip card, then we flip it and continue
                broadcast(connected, player if isinstance(player, str) else player[1], "was skipped")
                continue
            
            drew = False
            
            if isinstance(player, tuple):  # like above, if our first item is a tuple
                sock, player = player
                broadcast(connected, f"Its {player}'s turn! Current card is {fcard(played[-1])}")
                send_user(sock, "Its your turn!", fhand(hand))
                
                while True:
                    dec = send_input(sock, "Select your card: ")  # Ask the client for their card
                    
                    if dec.upper() == "DRAW":  # If they have no valid card, they may draw
                        drew = True
                        break

                    if not dec.isdigit():  # Technically 0 is a valid index, but negative numbers are not
                        send_user(sock, "That isnt a valid index! Send a number!")
                    elif (int(dec) - 1) > len(hand):  # Zero will just wrap around to the last item
                        send_user(sock, f"That is an invalid index! You only hand {len(hand)} cards!")
                    else:  # Ensure its a valid play or wild card
                        idx = int(dec) - 1
                        ncard = hand[idx % len(hand)] # The index we get is going to be regular counting not 0-based
                        
                        if ncard[0].startswith("WILD") or (ncard[0] == played[-1][0] or ncard[1] == played[-1][1]):
                            card = hand.pop(idx)  # Pop the item if its valid
                            
                            if not hand:
                                broadcast(connected, player, "won!")  # This is our win condition
                                return  # They've run out of cards, they win! We dont have an Uno call unfortunately
                            break
                        else:
                            send_user(sock, f"You cannot play {fcard(ncard)} on a {fcard(played[-1])} try again!")  # Until they play a valid card, send this
                        
                if not drew and card[0].startswith("WILD"):  # If the player played a card and that card is a wild card
                    while True:
                        newcolor = send_input(sock, "Select a color (RED, YELLOW, GREEN, BLUE): ").upper()  # We ask until we get a valid color

                        if newcolor not in colors:
                            send_user(sock, "That color is invalid! Try again")
                        else:
                            card = ("WILD", newcolor)  # So, we have ("WILD", "ALL"), but when its played it actually becomes a ("WILD", color)
                            break  # Thus if the start card is a ("WILD", "ALL") then you might just restart the game or play another wild card

            # The bot starts here
            else:
                broadcast(connected, f"It is {player}'s turn!")
                time.sleep(randint(1, 4))
                # Valid choices the bot can make
                choices = [j for j, item in enumerate(hand) if item[0].startswith("WILD") or (item[0] == played[-1][0] or item[1] == played[-1][1])]
                if not choices:  # If NO plays are valid, bot has to draw
                    drew = True
                else:  # Its just going to find all valid choices, and play randomly
                    card = hand.pop(choice(choices)) # Get a random card that is valid
                    if card[0].startswith("WILD"):  # If its a wildcard
                        count = Counter(item[1] for item in hand)
                        color, n = max(count.items(), key=lambda x: x[1], default=(choice(colors), 0))
                        card = (card[0], color)  # Pick the color that matches the color we have the most of

            if not drew:  # If the player didnt draw
                ndraw = 0
                if card[0] in ("DRAW2", "WILD4"):  # No need to switch, if its one of these grab the last char
                    ndraw += int(card[0][-1])  # Technically we can mod this for special draws

                if card[0] == "REVERSE":  # We really just reverse the play order, if the player is the last player
                    play_order.reverse()  # They might get to play twice. Truth is I'm lazy

                if card[0] == "SKIP":  # Set the condition, itll be switched next loop around and we'll skip the player
                    skipped = True
                    
                broadcast(connected, f"{player} played {fcard(card)}")
                played.append(card)
                if ndraw:  # Draw the cards
                    play_order[(i + 1) % len(play_order)][1].extend(draw_card(deck, played) for _ in range(ndraw)) # grab the next player, grab his hand and extend it randomly
                    name = play_order[(i + 1) % len(play_order)][0]  # If we overflow, we just % it back to the max
                    if isinstance(name, tuple):  # Regularize name
                        name = name[1]
                    broadcast(connected, name, f"drew {ndraw} cards")
            else:
                hand.append(draw_card(deck, played))
                broadcast(connected, player, "drew a card")


def connect_names(maxconnections, connect_timeout, username_timeout, host='0.0.0.0', port=5555):
    """Creates the socket and waits for users to connect, then gets their names"""
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # A generic listening socket
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    connection.bind(('0.0.0.0', 5555))  # Hosts by default on 0.0.0.0:5555
    connection.listen(maxconnections)  # Can only listen for maxconnections

    connected = await_connect(connection, maxconnections, connect_timeout)
    usernames = await_usernames(connected, username_timeout)

    return connection, usernames

def await_connect(sock, maxconnections, timeout):
    """Wait for users to connect, max users"""
    stime = time.monotonic()  # Monotonic is cool
    connected = []
    while len(connected) != maxconnections:
        rr, wr, er = select.select([sock], [], [], timeout * 1000)
        if rr:
            sock, (addr, port) = rr[0].accept()
            connected.append(sock)
            broadcast(connected, f"{addr}:{port} connected!")
        timeout = timeout - (stime - time.monotonic())
        if timeout <= 0:  # We break when timeout is reached with whatever players connected
            break
    if not connected:
        raise TimeoutError("Nobody connected!")  # If nobody connects just raise

    return connected

def await_usernames(connected, timeout):
    stime = time.monotonic()
    named = {}
    cnum = len(connected)
    all = connected[::]
    while len(named) < cnum:
        rr, wr, er = select.select(connected, [], [], timeout * 1000)
        timeout = timeout - (stime - time.monotonic())

        for sock in rr:
            name = sock.recv(1024).decode()
            named[sock] = name
            addr, port = sock.getsockname()
            broadcast(all, f"{addr}:{port} has chosen name {name}!")
            connected.remove(sock)  # No need to wait anymore, we have their name
        
        if timeout <= 0:
            break

    if not named:
        raise TimeoutError("Nobody sent a name!")

    for sock in connected:  # If someone doesnt connect in time, we just close the connection
        sock.send(json.dumps({"error": "You didn't send a name in time!"}).encode())
        sock.close()

    return named

def broadcast(connected, *message):
    """Send a message to all connected, varargs are connected with a space like print"""
    message = " ".join(message)
    print(message)
    for sock in connected:
        sock.send(json.dumps({"message": message}).encode() + b"\n")

def send_user(user, *message):
    """Send a message to a single socket"""
    message = " ".join(message)
    user.send(json.dumps({"message": message}).encode() + b"\n")

def send_input(user, *message):
    """Send a request for input from a single user"""
    message = " ".join(message)
    user.send(json.dumps({"input": message}).encode() + b"\n")
    return user.recv(1024).decode()  # Grab a big message pray it isnt too big

def run_game(maxplayers, addr='0.0.0.0', port=5555,
             ai_players=0, ctimeout=60, utimeout=60):
    """Run a game with the given variables"""
    connection, connected = connect_names(maxplayers,
                                          ctimeout,
                                          utimeout)
    
    start(connected, ai_players)
    for sock in connected:
        sock.close()
    connection.close()
    

if __name__ == "__main__":
    run_game(1, ai_players=5)
            
