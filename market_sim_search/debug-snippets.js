function searchForObjects(obj, keyMatch, path = 'window', depth = 0, maxDepth = 3, found = [],
                                 searched = new WeakSet()) {
    function isPrimitive(test) {
        return test !== Object(test);
    }

    if (obj === null || isPrimitive(obj) || depth > maxDepth || searched.has(obj)) {
        return found;
    }
    searched.add(obj);

    Object.keys(obj).forEach(key => {
        const value = obj[key];
        if (key.toLowerCase().includes(keyMatch)) {
            found.push({
                path: `${path}.${key}`,
                type: typeof value,
                value: typeof value === 'function' ? 'Function' : value
            });
        }
        if (!isPrimitive(value)) {
            searchForObjects(value, `${path}.${key}`, depth + 1, maxDepth, found, searched);
        }
    });
    return found;
}
