#!/usr/bin/python

import curses, time, pickle, sys, os, random, gzip

os.chdir(os.path.dirname(sys.argv[0]) or ".")

ENC = "UTF-8"

"""
Notes:
alignments: 0 = none, 1 = earth, 2 = air, 3 = fire, 4 = water
"""
ITEMS = {}
CRAFTING = {}

WINDOWSIZE = {0: 24, 1: 80}

def biasedRandom(lo, hi, target, steps=1):
	"""Return a random number between lo and hi; that is more likely to be near target. Increasing steps will increase likely hood of being close to target."""
	if lo >= hi:
		raise ValueError("lo should be less than hi")
	elif target < lo or target >= hi:
		raise ValueError("target not in range(lo, hi)")
	else:
		num = random.randint(lo, hi)
		for i in range(steps):
			num += int(random.random() * (target - num))
		return num

def biasedRandomChoice(lst, index, steps=1):
	"""Return a random element from list lst, that is more likely to be near index."""
	return lst[biasedRandom(0, len(lst)-1, index, steps)]

class Curses_screen:
	"""Nice curses screen for use in 'with' statements.
	
	https://www.ironalbatross.net/wiki/index.php5?title=Python_Curses"""
	def __enter__(self):
		self.stdscr = curses.initscr()
		curses.cbreak()
		curses.noecho()
		self.stdscr.keypad(1)
		return self.stdscr
	def __exit__(self,a,b,c):
		curses.nocbreak()
		self.stdscr.keypad(0)
		curses.echo()
		curses.endwin()

class World(object):
	"""Front end to a dictionary, functions the same, except that if Key is not found, it is created."""
	def __init__(self):
		self.__data = {(0,0): self.__genterrain(True)}
	def __getitem__(self, key):
		try:
			return self.__data[key]
		except KeyError:
			self.__data[key] = self.__genterrain()
			return self.__data[key]
	def __setitem__(self, key, value):
		self.__data[key] = value
	def __genterrain(self, spawn=False):
		data = b""
		terrain = [2,2,2,2,7,4,6,5,5,8,8,1]
		for i in range((WINDOWSIZE[0]-1)*WINDOWSIZE[1]):
			terrain[0] = biasedRandomChoice(terrain, 0, steps=3)
			data += bytes([terrain[0]])
		return data

class Game(object):
	"""Master game object"""
	def __init__(self, gamename, player, seed=None):
		self.gamename = gamename
		self.player = player
		self.seed = seed
		self.pos = 0,0, int((WINDOWSIZE[0]-2)/2), int(WINDOWSIZE[1]/2) # Center
		self.world = World()
		self.windowsize = WINDOWSIZE
	def slowmove(self, dr=(0,0)):
		"""Move target one space at a time"""
		if self.pos[2] + dr[0] > WINDOWSIZE[0]-2 or self.pos[3] + dr[1] > WINDOWSIZE[1]-1 or self.pos[2] + dr[0] < 0 or self.pos[3] + dr[1] < 0: return
		self.pos = (self.pos[0], self.pos[1], self.pos[2] + dr[0], self.pos[3] + dr[1])
	def bigmove(self, dr=(0,0)):
		"""Move to next screen"""
		self.pos = (self.pos[0] + dr[0], self.pos[1] + dr[1], self.pos[2], self.pos[3] )
	def dig(self):
		"""Replace the item at target with it's .replacewith propery, if the player has enough strenght"""
		index = WINDOWSIZE[1] * self.pos[2] + self.pos[3]
		item = self.world[self.pos[:2]][index]
		if item == 1: return True # special case for pits.
		if ITEMS[item].life < 0 or ITEMS[item].life > self.player.damage()[ITEMS[item].alignment]:
			return False
		newitem = ITEMS[item].replacewith
		self.player.inv = ITEMS[item].drops + self.player.inv
		self.world[self.pos[:2]] = self.world[self.pos[:2]][:index] + bytes([newitem]) + self.world[self.pos[:2]][index+1:]
		return True
	def placeblock(self):
		"""Place a block at target."""
		index = WINDOWSIZE[1] * self.pos[2] + self.pos[3]
		newitem = None
		for i in range(len(self.player.inv)-1, -1, -1):
			if self.player.inv[i] < 256:
				newitem = self.player.inv.pop(i)
				break
		if newitem and self.dig():
			self.world[self.pos[:2]] = self.world[self.pos[:2]][:index] + bytes([newitem]) + self.world[self.pos[:2]][index+1:]
		
class Player(object):
	"""Player Class"""
	def __init__(self, name, pos=None, inv=[]):
		self.name = name
		self.pos = pos or (int((WINDOWSIZE[0]-2)/2), int(WINDOWSIZE[1]/2))
		self.inv = inv
		self.equipped = []
		self.bear = 0
		self.strength = 10
		#self.damage = property(self.__damage)
	def move(self, game, dr=(0,0)):
		old = self.pos
		if self.pos[0] + dr[0] > WINDOWSIZE[0]-2 or self.pos[1] + dr[1] > WINDOWSIZE[1]-1 or self.pos[0] + dr[0] < 0 or self.pos[1] + dr[1] < 0:
			self.pos = (self.pos[0] + (WINDOWSIZE[0]-2)*-dr[0], self.pos[1] + (WINDOWSIZE[1]-1)*-dr[1])
			if not ITEMS[game.world[game.pos[:2]][(WINDOWSIZE[1]) * game.pos[2] + game.pos[3]]].walkable:
				self.pos = old
				return (0,0)
			return dr
		self.pos = (self.pos[0] + dr[0], self.pos[1] + dr[1])
		if not ITEMS[game.world[game.pos[:2]][(WINDOWSIZE[1]) * self.pos[0] + self.pos[1]]].walkable:
			self.pos = old
		return (0,0)
	def damage(self):
		alignments = [0,1,1,1,1]
		for item in self.equipped:
			alignments[ITEMS[item].alignment] += ITEMS[item].damage
		return tuple(alignments)

class Item(object):
	def __init__(self, alignment, name, char, weight, life, replacewith, drops, walkable, damage):
		self.alignment = alignment
		self.name = name
		self.char = char
		self.weight = weight
		self.life = life
		self.replacewith = replacewith
		self.drops = drops
		self.walkable = walkable
		self.damage = damage

def load_world(name):
	if not name.endswith(".savefile"):
		name += ".savefile"
	with gzip.GzipFile(name, "rb") as world_file:
		return pickle.load(world_file)

def save_world(game, name=None):
	if name is None:
		name = game.gamename
	name += ".savefile"
	with gzip.GzipFile(name, "wb") as save_file:
		pickle.dump(game, save_file)

def showmap(game, window, alert=None):
	help_text = "Q: Quit; WASD: Move Player; G: Dig/Pick up; I: Inv; O: Options".center(WINDOWSIZE[1]-1)
	window.addstr(0,0,"".join([ITEMS[item].char for item in game.world[game.pos[:2]]])) # Print the map
	window.addch(game.player.pos[0], game.player.pos[1], "X", curses.A_REVERSE + curses.A_BOLD) # Add the player to the map
	window.addch(game.pos[2], game.pos[3], window.inch(game.pos[2], game.pos[3]), curses.A_REVERSE) # Add the target to the map
	if alert: window.addstr((WINDOWSIZE[0]-2)*(game.player.pos[0] != (WINDOWSIZE[0]-2) and game.pos[2] != (WINDOWSIZE[0]-2)),0,alert.center((WINDOWSIZE[1]-1)), curses.A_REVERSE) # Add an alert message to the bottom, or the top if either target or player is at the bottom
	window.addstr((WINDOWSIZE[0]-1),0,help_text, curses.A_REVERSE) # Add the help text to the bottom.
	window.refresh()

def mainmenu(win, menu=["New Game", "Load Game", "Quit"], default = 0):
	"""Function for displaying a full screen menu, menu wraps, but does not implement anything incase the menu is longer than the screen. Sorry."""
	if not menu: return None
	win.erase()
	selected = default
	row = 10
	while True:
		selected %= len(menu)
		for i in range(len(menu)):
			option = menu[i]
			win.addstr(10+i, 0, option.center((WINDOWSIZE[1]-1)), curses.A_REVERSE*(selected == i))
		win.refresh()
		move = win.getch()
		if move == curses.KEY_UP:
			selected -= 1
		elif move == curses.KEY_DOWN:
			selected += 1
		elif move in (10,32): # Enter / Space
			win.erase()
			return selected

def nicerange(center, length, mx=(WINDOWSIZE[0]-3)):
	"""Returns a tuple containing the start and end range of a list of length 'length' that centers on 'center' with maximum range 'mx'"""
	if length < mx: return (0,length)
	elif center < mx/2: return (0,mx)
	elif center > length-(mx/2): return (length-mx, length)
	else: return (int(center-(mx/2)), int(center+(mx/2)))

def lowtwo(number):
	return int(number/2)*2

def showinv(win, game):
	"""Show inventory."""
	help_text = "B: Back; Enter/Space: Equip/Unequip; D: Drop Item; C: Crafting".center(79)
	selected = ((len(game.player.inv) > 0) or 2*(len(game.player.equipped) > 0) or 3 + mainmenu(win, menu=["No items in Inventory!"])) - 1 , 0
	if selected[0] > 1: return
	while True:
		win.erase()
		win.addstr(0,0,"Unequipped".center(int(WINDOWSIZE[1]/2)) + "Equipped".center(int(WINDOWSIZE[1]/2)), curses.A_REVERSE)
		lists = (game.player.inv, game.player.equipped)
		selected = (selected[0], selected[1] % (len(lists[selected[0]]) or 1)) # abitrary 1, will never come into play if the len is 0, so w/e
		rng = nicerange(selected[1], len(lists[selected[0]]))
		for i in range(*rng):
			option = ITEMS[lists[selected[0]][i]].name.ljust((int(WINDOWSIZE[1]/2)-1))
			win.addstr(1+i-rng[0], (int(WINDOWSIZE[1]/2)+1)*(selected[0]), option, curses.A_REVERSE*(selected[1] == i))
		for i in range(*nicerange(0, len(lists[not selected[0]]))):
			option = ITEMS[lists[not selected[0]][i]].name.ljust((int(WINDOWSIZE[1]/2)-1))
			win.addstr(1+i, (int(WINDOWSIZE[1]/2)+1)*(not selected[0]), option)
		stats = ("Damage: %s; Bearing: %i" % (repr(game.player.damage()[1:]), game.player.bear)).center(WINDOWSIZE[1])
		win.addstr((WINDOWSIZE[0]-2),0,stats,curses.A_REVERSE)
		win.addstr((WINDOWSIZE[0]-1),0,help_text, curses.A_REVERSE)
		win.refresh()
		move = win.getch()
		if move in (ord("b"), ord("q")):
			return
		elif move in (curses.KEY_LEFT, curses.KEY_RIGHT):
			if lists[not selected[0]]:
				selected = (not selected[0], selected[1])
		elif move == curses.KEY_UP:
			selected = (selected[0], selected[1] - 1)
		elif move == curses.KEY_DOWN:
			selected = (selected[0], selected[1] + 1)
		elif move in (10,32): # Enter / Space
			if ITEMS[lists[selected[0]][selected[1]]].weight + (-selected[0] or 1)*game.player.bear <= game.player.strength:
				game.player.bear += (-selected[0] or 1)*ITEMS[lists[selected[0]][selected[1]]].weight
				lists[not selected[0]].append(lists[selected[0]].pop(selected[1]))
			if not lists[selected[0]]: # If they exhaust the list
				selected = (not selected[0], selected[1])
		elif move in (ord("d"), ):
			lists[selected[0]].pop(selected[1])
		elif move in (ord("c"), ):
			showcrafting(win, game)
		elif move in (ord("0"), ):
			lists[selected[0]].append(lists[selected[0]].pop(selected[1]))

def showcrafting(win, game):
	"""Show crafting menu.
	
	Basically the same as showinv, but has a few subtle differences."""
	help_text = "B: Back; Enter/Space: Add/Remove; ~: Confirm".center(79)
	selected = 0,0
	crafting = []
	result = "".center(int(WINDOWSIZE[1]/2)-1)
	while True:
		win.erase()
		win.addstr(0,0,"Inventory".center(int(WINDOWSIZE[1]/2)) + "Crafting".center(int(WINDOWSIZE[1]/2)), curses.A_REVERSE)
		lists = (game.player.inv, crafting)
		selected = (selected[0], selected[1] % (len(lists[selected[0]]) or 1)) # abitrary 1, will never come into play if the len is 0, so w/e
		rng = nicerange(selected[1], len(lists[selected[0]]))
		for i in range(*rng):
			option = ITEMS[lists[selected[0]][i]].name.ljust(int(WINDOWSIZE[1]/2)-1)
			win.addstr(1+i-rng[0], (int(WINDOWSIZE[1]/2)+1)*(selected[0]), option, curses.A_REVERSE*(selected[1] == i))
		for i in range(*nicerange(0,len(lists[not selected[0]]))):
			option = ITEMS[lists[not selected[0]][i]].name.ljust(39)
			win.addstr(1+i, (int(WINDOWSIZE[1]/2)+1)*(not selected[0]), option)
		
		win.addstr((WINDOWSIZE[0]-2),(int(WINDOWSIZE[1]/2)+1),result, curses.A_REVERSE)
		win.addstr((WINDOWSIZE[0]-1),0,help_text, curses.A_REVERSE)
		win.refresh()
		move = win.getch()
		if move in (ord("b"), ord("q")):
			game.player.inv + crafting
			return
		elif move in (curses.KEY_LEFT, curses.KEY_RIGHT):
			if lists[not selected[0]]:
				selected = (not selected[0], selected[1])
		elif move == curses.KEY_UP:
			selected = (selected[0], selected[1] - 1)
		elif move == curses.KEY_DOWN:
			selected = (selected[0], selected[1] + 1)
		elif move in (10,32): # Enter / Space
			lists[not selected[0]].append(lists[selected[0]].pop(selected[1]))
			if not lists[selected[0]]: # If they exhaust the list
				selected = (not selected[0], selected[1])
		elif move in (ord("~"), ):
			try:
				game.player.inv.append(CRAFTING[tuple(crafting)])
				crafting = []
			except KeyError:
				pass
		crafting.sort()
		try:
			result = ITEMS[CRAFTING[tuple(crafting)]].name.center(39)
		except KeyError:
			result = "".center(int(WINDOWSIZE[1]/2)-1)

def main():
	with open("items.txt") as itemfile:
		noplace = {"char": "", "life": 0, "replacewith": -1, "drops": [], "walkable": None}
		ITEMS.update(eval(itemfile.read())) # Load Items
	with open("crafting.txt") as craftingfile:
		CRAFTING.update(eval(craftingfile.read())) # Load Crafting options
	with Curses_screen() as win:
		height,width = win.getmaxyx()
		if height < 12 or width < 80:
			raise ValueError("Terminal is not the right size!")
		WINDOWSIZE.update({0: height, 1: width})
		while True:
			choice = mainmenu(win)
			if choice == 0: # New Game
				curses.echo()
				win.addstr(10,0, "Enter a name for the world:")
				win.addstr(" ")
				win.refresh()
				gamename = win.getstr().decode(ENC)
				win.addstr(11,0, "And one for your player:")
				win.addstr(" ")
				win.refresh()
				playername = win.getstr().decode(ENC)
				curses.noecho()
				win.erase()
				game = Game(gamename, Player(playername))
				save_world(game)
				
			if choice == 1: # Load Game
				saves = [f for f in os.listdir(".") if f.endswith(".savefile")]
				if not saves:
					mainmenu(win, ["No Saved Worlds!"])
					continue
				worldfile = saves[mainmenu(win, saves)]
				game = load_world(worldfile)
				if game.windowsize != WINDOWSIZE:
					mainmenu(win, ["Savefile designed for different sized screen: %s" % repr(game.windowsize)])
					continue
			if choice == 2: # Quit
				return 0
			break
		alert = None
		while True:
			showmap(game, win, alert)
			command = win.getch()
			if command in (ord("q"), 27): #  Q or ESC
				lastwish = mainmenu(win, ["Save First", "Quit Without Saving", "Cancel"])
				if lastwish == 0:
					save_world(game)
					return 0
				elif lastwish == 1:
					return 0
			# Player movement
			elif command == ord("w"): game.bigmove(game.player.move(game, (-1,0)))
			elif command == ord("s"): game.bigmove(game.player.move(game, (1,0)))
			elif command == ord("a"): game.bigmove(game.player.move(game, (0,-1)))
			elif command == ord("d"): game.bigmove(game.player.move(game, (0,1)))
			# Target movement
			elif command == curses.KEY_UP: game.slowmove((-1,0))
			elif command == curses.KEY_DOWN: game.slowmove((1,0))
			elif command == curses.KEY_LEFT: game.slowmove((0,-1))
			elif command == curses.KEY_RIGHT: game.slowmove((0,1))
			# Dig
			elif command == ord("g"): game.dig()
			# Show inv
			elif command == ord("i"): showinv(win, game)
			# Place a block
			elif command in (10,32): game.placeblock() # Enter / Space
			
			alert = ITEMS[game.world[game.pos[:2]][WINDOWSIZE[1] * game.pos[2] + game.pos[3]]].name + (command == ord("c"))*(str(game.pos[:2]))
	return 0


if __name__ == '__main__':
	sys.exit(main())