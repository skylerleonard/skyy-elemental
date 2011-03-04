#!/usr/bin/python

import curses, time, pickle, sys, os, random, gzip

os.chdir(os.path.dirname(sys.argv[0]) or ".")

HELP_TEXT = "Q: Quit; WASD: Move Player; G: Dig/Pick up; I: Inv; O: Options".center(79)

ENC = "UTF-8"

"""
Notes:
alignments: 0 = none, 1 = earth, 2 = air, 3 = fire, 4 = water
"""
ITEMS = {}


def biasedRandom(lo, hi, target, steps=1):
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
		terrain = [2,2,2,2,7,4,6,5,1]
		for i in range(1840):
			if spawn and i == 920:
				data += b"\x00"
				continue
			terrain[0] = biasedRandomChoice(terrain, 0, steps=3)
			data += bytes([terrain[0]])
		return data

class Game(object):
	def __init__(self, gamename, player, seed=None):
		self.gamename = gamename
		self.player = player
		self.seed = seed
		self.pos = 0,0, 11,40
		self.world = World()
	
	def slowmove(self, dr=(0,0)):
		if self.pos[2] + dr[0] > 22 or self.pos[3] + dr[1] > 79 or self.pos[2] + dr[0] < 0 or self.pos[3] + dr[1] < 0: return
		self.pos = (self.pos[0], self.pos[1], self.pos[2] + dr[0], self.pos[3] + dr[1])
	def bigmove(self, dr=(0,0)):
		self.pos = (self.pos[0] + dr[0], self.pos[1] + dr[1], self.pos[2], self.pos[3] )
	def dig(self):
		index = 80 * self.pos[2] + self.pos[3]
		item = self.world[self.pos[:2]][index]
		if ITEMS[item].life < 0 or ITEMS[item].life > self.player.damage()[ITEMS[item].alignment]:
			return
		newitem = ITEMS[item].replacewith
		self.player.inv += ITEMS[item].drops
		self.world[self.pos[:2]] = self.world[self.pos[:2]][:index] + bytes([newitem]) + self.world[self.pos[:2]][index+1:]
		
class Player(object):
	def __init__(self, name, pos=(11,40), inv=[]):
		self.name = name
		self.pos = pos
		self.inv = inv
		self.equipped = []
		self.bear = 0
		self.strength = 10
		#self.damage = property(self.__damage)
	def move(self, game, dr=(0,0)):
		old = self.pos
		if self.pos[0] + dr[0] > 22 or self.pos[1] + dr[1] > 79 or self.pos[0] + dr[0] < 0 or self.pos[1] + dr[1] < 0:
			self.pos = (self.pos[0] + 22*-dr[0], self.pos[1] + 79*-dr[1])
			if not ITEMS[game.world[game.pos[:2]][80 * game.pos[2] + game.pos[3]]].walkable:
				self.pos = old
				return (0,0)
			return dr
		self.pos = (self.pos[0] + dr[0], self.pos[1] + dr[1])
		if not ITEMS[game.world[game.pos[:2]][80 * self.pos[0] + self.pos[1]]].walkable:
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
	window.addstr(0,0,"".join([ITEMS[item].char for item in game.world[game.pos[:2]]]))
	window.addch(game.player.pos[0], game.player.pos[1], "X")
	window.addch(game.pos[2], game.pos[3], window.inch(game.pos[2], game.pos[3]), curses.A_REVERSE)
	if alert: window.addstr(22*(game.player.pos[0] != 22 and game.pos[2] != 22),0,alert.center(79), curses.A_REVERSE)
	window.addstr(23,0,HELP_TEXT, curses.A_REVERSE)
	window.refresh()

def mainmenu(win, menu=["New Game", "Load Game", "Quit"], default = 0):
	if not menu: return None
	win.erase()
	selected = default
	row = 10
	while True:
		selected %= len(menu)
		for i in range(len(menu)):
			option = menu[i]
			win.addstr(10+i, 0, option.center(79), curses.A_REVERSE*(selected == i))
		win.refresh()
		move = win.getch()
		if move == curses.KEY_UP:
			selected -= 1
		elif move == curses.KEY_DOWN:
			selected += 1
		elif move in (10,32): # Enter / Space
			win.erase()
			return selected

def nicerange(center, length, mx=21):
	if length < mx: return (0,length)
	elif center < mx/2: return (0,mx)
	elif center > length-(mx/2): return (length-mx, length)
	else: return (int(center-(mx/2)), int(center+(mx/2)))

def showinv(win, game):
	help_text = "B: Back; Enter/Space: Equip/Unequip; D: Drop Item".center(79)
	selected = 0,0
	while True:
		win.erase()
		win.addstr(0,0,"Unequipped".center(40) + "Equipped".center(40), curses.A_REVERSE)
		lists = (game.player.inv, game.player.equipped)
		selected = (selected[0], selected[1] % (len(lists[selected[0]]) or 1)) # abitrary 1, will never come into play if the len is 0, so w/e
		rng = nicerange(selected[1], len(lists[selected[0]]))
		for i in range(*rng):
			option = ITEMS[lists[selected[0]][i]].name.ljust(39)
			win.addstr(1+i-rng[0], 41*(selected[0]), option, curses.A_REVERSE*(selected[1] == i))
		for i in range(*nicerange(0, len(lists[not selected[0]]))):
			option = ITEMS[lists[not selected[0]][i]].name.ljust(39)
			win.addstr(1+i, 41*(not selected[0]), option)
		stats = ("Damage: %s; Bearing: %i" % (repr(game.player.damage()[1:]), game.player.bear)).center(80)
		win.addstr(22,0,stats,curses.A_REVERSE)
		win.addstr(23,0,help_text, curses.A_REVERSE)
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
		elif move in (ord("d"), ):
			lists[selected[0]].pop(selected[1])

def main():
	with open("items.txt") as itemfile:
		ITEMS.update(eval(itemfile.read()))
	with Curses_screen() as win:
		height,width = win.getmaxyx()
		if not (height == 24 or width == 80):
			raise ValueError("Terminal is not thr right size! Should be 80x24.")
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
			if choice == 2: # Quit
				return 0
			break
		alert = None
		while True:
			showmap(game, win, alert)
			command = win.getch()
			if command == ord("q"):
				lastwish = mainmenu(win, ["Save First", "Quit Without Saving", "Cancel"])
				if lastwish == 0:
					save_world(game)
					return 0
				elif lastwish == 1:
					return 0
				
			elif command == ord("w"): game.bigmove(game.player.move(game, (-1,0)))
			elif command == ord("s"): game.bigmove(game.player.move(game, (1,0)))
			elif command == ord("a"): game.bigmove(game.player.move(game, (0,-1)))
			elif command == ord("d"): game.bigmove(game.player.move(game, (0,1)))
			
			elif command == curses.KEY_UP: game.slowmove((-1,0))
			elif command == curses.KEY_DOWN: game.slowmove((1,0))
			elif command == curses.KEY_LEFT: game.slowmove((0,-1))
			elif command == curses.KEY_RIGHT: game.slowmove((0,1))
			
			elif command == ord("g"): game.dig()
			
			elif command == ord("i"): showinv(win, game)
			
			alert = ITEMS[game.world[game.pos[:2]][80 * game.pos[2] + game.pos[3]]].name
	return 0


if __name__ == '__main__':
	sys.exit(main())