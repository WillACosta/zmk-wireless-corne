/*
 * Copyright (c) 2026 The ZMK Contributors
 * SPDX-License-Identifier: MIT
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/event_manager.h>

#if IS_ENABLED(CONFIG_ZMK_KEYMAP)
#include <zmk/events/layer_state_changed.h>
#include <zmk/events/keycode_state_changed.h>
#endif

LOG_MODULE_REGISTER(zmk_heatmap, CONFIG_ZMK_HEATMAP_LOG_LEVEL);

static uint8_t active_layer = 0;

#if IS_ENABLED(CONFIG_ZMK_KEYMAP)
static int zmk_heatmap_layer_listener_cb(const zmk_event_t *eh) {
    struct zmk_layer_state_changed *ev = as_zmk_layer_state_changed(eh);
    if (ev != NULL && ev->state) {
        active_layer = ev->layer;
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(zmk_heatmap_layer, zmk_heatmap_layer_listener_cb);
ZMK_SUBSCRIPTION(zmk_heatmap_layer, zmk_layer_state_changed);

static int zmk_heatmap_keycode_listener_cb(const zmk_event_t *eh) {
    struct zmk_keycode_state_changed *ev = as_zmk_keycode_state_changed(eh);
    if (ev != NULL && ev->state) {
        int64_t timestamp = k_uptime_get();
        LOG_INF("HM:KC:0x%02X,0x%04X,%lld", ev->usage_page, ev->keycode, timestamp);
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(zmk_heatmap_keycode, zmk_heatmap_keycode_listener_cb);
ZMK_SUBSCRIPTION(zmk_heatmap_keycode, zmk_keycode_state_changed);
#endif

static int zmk_heatmap_position_listener_cb(const zmk_event_t *eh) {
    struct zmk_position_state_changed *ev = as_zmk_position_state_changed(eh);
    if (ev != NULL) {
        if (ev->state) {
            int64_t timestamp = k_uptime_get();
            LOG_INF("HM:%u,%u,%lld", ev->position, active_layer, timestamp);
        }
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(zmk_heatmap_position, zmk_heatmap_position_listener_cb);
ZMK_SUBSCRIPTION(zmk_heatmap_position, zmk_position_state_changed);
