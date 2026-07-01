## Project Status Update

The development team has completed the initial implementation of the
core simulation engine. Key milestones achieved this sprint include:

- Modular generator architecture with plugin support
- Configurable scheduling engine with multiple scenario profiles
- Structured event logging with JSON Lines format
- Comprehensive reporting with JSON, CSV, and HTML output

Next steps involve integration testing and performance optimization
to ensure the tool meets the specified resource constraints.Array/**
 * Sample JavaScript module for VS Code adapter testing.
 *
 * This file is used by the Developer Activity Simulator to test
 * VS Code interactions like opening files, editing, and saving.
 */

class EventBus {
    constructor() {
        /** @type {Map<string, Function[]>} */
        this.handlers = new Map();
        this.history = [];## Project Status Update

        The development team has completed the initial implementation of the
        core simulation engine. Key milestones achieved this sprint include:

        - Modular generator architecture with plugin support
        - Configurable scheduling engine with multiple scenario profiles
        - Structured event logging with JSON Lines format
        - Comprehensive reporting with JSON, CSV, and HTML output

        Next steps involve integration testing and performance optimization
        to ensure the tool meets the specified resource constraints.Array
    }

    /**
     * Register an event handler.
     * @param {string} event - Event name
     * @param {Function} handler - Handler function
     * @returns {EventBus} this instance for chaining
     */
    on(event, handler) {
        if (!this.handlers.has(event)) {
            this.handlers.set(event, []);
        }
        this.handlers.get(event).push(handler);
        return this;
    }

    /**
     * Emit an event with optional data.
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emit(event, data) {
        const timestamp = new Date().toISOString();
        this.history.push({ event, data, timestamp });

        const handlers = this.handlers.get(event) || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`Handler error for ${event}:`, error);
            }
        });
    }

    /**
     * Remove all handlers for an event.
     * @param {string} event - Event name
     */
    off(event) {
        this.handlers.delete(event);
    }

    /**
     * Get event history.
     * @returns {Array} Array of historical events
     */
    getHistory() {
        return [...this.history];
    }
}

/**
 * Simple data transformation utilities.
 */
const DataUtils = {
    /**
     * Group array items by a key function.
     * @param {Array} items - Items to group
     * @param {Function} keyFn - Function to extract group key
     * @returns {Object} Grouped items
     */
    groupBy(items, keyFn) {
        return items.reduce((groups, item) => {
            const key = keyFn(item);
            if (!groups[key]) {
                groups[key] = [];
            }
            groups[key].push(item);
            return groups;
        }, {});
    },

    /**
     * Calculate statistics for a numeric array.
     * @param {number[]} values - Numeric values
     * @returns {Object} Statistics object
     */
    stats(values) {
        if (values.length === 0) {
            return { count: 0, sum: 0, mean: 0, min: 0, max: 0 };
        }

        const sum = values.reduce((a, b) => a + b, 0);
        return {
            count: values.length,
            sum,
            mean: sum / values.length,
            min: Math.min(...values),
            max: Math.max(...values),
        };
    },

    /**
     * Flatten a nested array.
     * @param {Array} arr - Nested array
     * @returns {Array} Flattened array
     */
    flatten(arr) {
        return arr.reduce(
            (flat, item) =>
                flat.concat(Array.isArray(item) ? this.flatten(item) : item),
            []
        );
    },
};

// Example usage
const bus = new EventBus();
bus.on("data:loaded", (data) => console.log("Data loaded:", data));
bus.emit("data:loaded", { records: 42 });

module.exports = { EventBus, DataUtils };
