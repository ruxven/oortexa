#!/bin/bash
echo "Docker build script running!"
if [ -f "Makefile" ]; then
    make
else
    echo "No Makefile found, just echo success."
    echo "This is the polymorphic script in action."
fi
