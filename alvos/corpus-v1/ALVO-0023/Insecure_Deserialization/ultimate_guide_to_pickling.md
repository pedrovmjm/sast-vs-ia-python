## Found online here: https://snyk.io/blog/guide-to-python-pickle/



This article will teach you how to safely use pickle in your applications. While pickle is incredibly convenient to use in a number of situations, it’s important to note that you should **only** unpickle data that you trust! Unpickling untrusted data can lead to arbitrary code execution and is a common source of critical security vulnerabilities.

## How to use Python pickle

Pickle is straightforward to use, so let’s jump right in. All relevant functions for pickling and unpickling are in the pickle module. So, let’s start by importing that module.

```python
import pickle
```

When pickling a Python object, we can either pickle it directly into a file or into a bytes object that we can use later in our code. In both cases, all it takes is a simple method call.

To pickle an object into a file, call `pickle.dump(object, file)`. To get just the pickled bytes, call `pickle.dumps(object)`.

As mentioned, pickle is easily usable in Python. You can pickle many data types, such as:

-   Python primitives
-   Nested collection structures like tuples, lists, sets, and dictionaries — so long as the dictionaries contain only pickleable objects
-   Most class instances

Python’s documentation contains an [exhaustive list](https://docs.python.org/3/library/pickle.html#what-can-be-pickled-and-unpickled) of what can be pickled.

If you try to pickle an unpickable object, Python raises a `PicklingError`.

## Python pickle examples

Let’s practice pickling. Below is a data structure that represents the state of a hypothetical game. This game has a player that stands at a certain location in the game world, represented as a tuple of coordinates. The world also has obstacles at given locations, represented as tuples. The player owns items that have a name and a cost. The classes look like this:

```python
class GameItem:
    def __init__(self, name, cost):
        self.name = name
        self.cost = cost

class GameState:
    def __init__(self, player_coordinates, obstacles, items):
        self.player = player_coordinates # tuple (x, y)
        self.obstacles = obstacles # set of tuples (x, y)
        self.items = items # list of GameItems
```

Now, let’s construct a specific state and pickle it into a file.

```python
player = (3, 2)
obstacles = { (1, 1), (5, 6), (7, 4), (0, -1) }
items = [ GameItem("Sword", 500), GameItem("Potion", 150) ]

state = GameState(player, obstacles, items)
with open("state.bin", "wb") as f: # "wb" because we want to write in binary mode
    pickle.dump(state, f)
```

Pickle is a human-unreadable binary format, so if we investigate the contents of our newly created `state.bin` file, it won’t make much sense. We’ll only recognize some identifier names, such as `GameState` and `obstacles`.

Now that we’ve saved the game state into a file, let’s try to load the state from that file so we can build save and resume functionality into our game! Both `pickle.dump` and `pickle.dumps` have their counterparts for unpickling: `pickle.load(file)` loads a pickled Python object from a file, `pickle.loads(bytes)` does the same for the given bytes.

```python
with open("state.bin", "rb") as f: # "rb" because we want to read in binary mode
    state = pickle.load(f)

print("Player coordinates:", state.player)
print("Obstacles:", state.obstacles)
print("Number of items:", len(state.items))
```

As you can see, the basics of pickling are very simple. It only takes a method call to store and load a Python object.

## How to exploit Python pickle

As mentioned in the introduction, you should **only** unpickle data you trust because **the pickle module isn’t secure**. If you unpickle an attacker’s byte stream, you could execute arbitrary code. This is a side effect of how powerful the pickle format is. 

A Python object can specify how it should be pickled using the special [_reduce_](https://docs.python.org/3/library/pickle.html#object.__reduce__) method. This method should either return a string or a tuple. A string represents the name of a global variable. A tuple represents callable code (such as a function or class), the arguments to the callable code, and some optional information that isn’t relevant for this example. The process of unpickling calls the specified callable code with its arguments.

Using this knowledge, you can construct a pickled object that calls an arbitrary function you want to run during unpickling. For example, you could execute a system command by executing the `os.system` function during unpickling, or `eval` to execute any Python code you want!

Here’s an (innocent) example of this attack, using the `eval` function (which will simply call the `print` function when loaded):

```python
import pickle

class Attack:
    def __reduce__(self):
        return (eval, ("print(1+2)",))

malicious = pickle.dumps(Attack())

pickle.loads(malicious)
```

If we run this code, it will print the number 3 on the console because unpickling this data will execute `eval("print(1+2)")`.

## How to safely use Python pickle

If you must accept data from an untrusted client, you can’t use pickle due to the risks mentioned above. Instead, you should use another data serialization format such as JavaScript Object Notation ([JSON](https://www.json.org/json-en.html)). 

It’s possible to do this using [Python’s json module](https://docs.python.org/3/library/json.html#module-json). The downside being that the `json` module is much less potent than pickle because it doesn’t support complicated data types, such as custom objects, out of the box. Also, the native data types of JSON are limited. For example, a set in Python has no equivalent in JSON, so you would have to use a custom encoder for sets. However, JSON is a safe format when dealing with untrusted data.

Suppose a trusted application generates pickled data, but you can’t guarantee its integrity between the time the data is pickled and unpickled. Maybe you can’t trust the data because you’re sending the pickled data over an insecure network, or you’re saving it in persistent storage that an attacker might be able to access. 

In either case, one solution is to generate a cryptographic signature for the pickled data using an HMAC. The pickled data is then sent or stored together with the signature. Before unpickling, the receiver can validate the signature to check the integrity of the pickled data. 

You can generate a signature like this (using SHA256):

```python
SECRET_KEY = b"your secret key here"
obj = [ "test", (1, 2), [ "a", "b" ] ]
data = pickle.dumps(obj)
digest = hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()
```

**NOTE**: In the real world, your secret key would be stored securely within a server-side application that is never exposed to any untrusted environment. Please do not hardcode a secret key into your codebase. =)

The receiver can calculate the expected digest for the pickled data and check if it matches the given digest.

```python
expected_digest = hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()
if expected_digest != digest:
    print("Data integrity violated")
else:
    unpickled = pickle.loads(data)
    print(unpickled)
```

In this scenario, even if attackers tamper with the pickled data, they won’t be able to successfully tamper with the signature (or trick the receiver into running untrusted code) if they don’t have the secret key.

## Final thoughts

You now know how to use Python’s pickle module to serialize and deserialize complex Python objects in a secure way, and that’s a pretty big dill.

Remember, because pickle can cause critical security vulnerabilities in code, you should never unpickle data you don’t trust. If you must accept data from an untrusted client, you should use the safer JSON format. And, if you transfer pickled data between trusted applications but need extra measures to prevent tampering, you should generate an HMAC signature you can verify before unpickling.
