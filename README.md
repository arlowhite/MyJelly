# MyJelly

This is based on an idea I have for making a game where kids can draw and animate various sea creatures using meshes.
The user imports a picture, selects Control Points, then drags them to the open and closed Jelly bell positions to animate it.
The code is a bit ugly for my standards due to a number of refactors as I learned Kivy and worked on the design.

## Kivy Thoughts

I thought it would be fun and hopefully faster to use Python for this prototype project and decided upon Kivy for the game
engine for its focus on mobile apps.
Unfortunately, there are some significant performance issues with Kivy, in particular the long startup time is a
frustration and I worry about scaling up the game in the future. In addition Kivy is fairly young in its development so
along the way I encountered a few bugs and issues with documentation and the build system.
Along the way, I did discover [KivEnt](http://kivent.org) - 
an [Entity Component System](https://en.wikipedia.org/wiki/Entity_component_system) for Kivy, which improves performance
by taking advantage of Cython.
I found the potential for an ECS architecture to address cross-cutting concerns intriguing as an Object-Oriented design
quickly becomes awkward when coding a game (and other large applications).
However, converting to KivEnt would be a significant task at this point and I think a mature game engine such as Unity is
a better choice if I decide to start over.
