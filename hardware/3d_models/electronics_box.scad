// Electronics Belt Box
// Holds Arduino Due + NeuroStimDuino stacked
//
// Parameters
inner_length = 100;     // Arduino Due ~101mm, snug fit
inner_width = 55;       // Arduino Due ~53mm + clearance
inner_height = 35;      // Stack height: Due (~11mm) + shield (~15mm) + cables
wall = 2.0;             // Wall thickness (mm)
corner_r = 3;           // Corner radius (mm)
lid_lip = 1.5;          // Lid engagement depth (mm)
vent_slots = 5;         // Number of ventilation slots
cable_port_w = 25;      // Cable exit port width (mm)
cable_port_h = 12;      // Cable exit port height (mm)
belt_clip_w = 40;       // Belt clip width (mm)
belt_clip_gap = 5;      // Belt clip gap (belt thickness) (mm)
belt_clip_depth = 15;   // Belt clip depth (mm)
$fn = 30;

module rounded_box(l, w, h, r) {
    hull() {
        for (x = [-l/2 + r, l/2 - r])
            for (y = [-w/2 + r, w/2 - r])
                translate([x, y, 0])
                    cylinder(r=r, h=h);
    }
}

module box_body() {
    difference() {
        // Outer shell
        rounded_box(inner_length + wall*2, inner_width + wall*2,
                     inner_height + wall, corner_r);

        // Inner cavity
        translate([0, 0, wall])
            rounded_box(inner_length, inner_width,
                         inner_height + 1, corner_r - wall/2);

        // Cable exit port (one short end)
        translate([inner_length/2 + wall, 0, wall + cable_port_h/2 + 2])
            rotate([0, 90, 0])
                rounded_box(cable_port_h, cable_port_w, wall * 3, 2);

        // Ventilation slots (top)
        for (i = [0:vent_slots-1]) {
            x_pos = -inner_length/3 + i * (inner_length * 2/3) / (vent_slots - 1);
            translate([x_pos, 0, inner_height + wall - 0.1])
                cube([3, inner_width * 0.6, wall + 0.2], center=true);
        }

        // USB access port (other short end, for programming)
        translate([-(inner_length/2 + wall), 0, wall + 5])
            rotate([0, 90, 0])
                rounded_box(8, 14, wall * 3, 2);
    }

    // Arduino mounting posts (4 corners, M3)
    for (x = [-inner_length/2 + 5, inner_length/2 - 5])
        for (y = [-inner_width/2 + 5, inner_width/2 - 5])
            translate([x, y, wall])
                difference() {
                    cylinder(r=2.5, h=3);
                    translate([0, 0, -0.1])
                        cylinder(r=1.3, h=3.2);  // M3 hole
                }
}

module belt_clip() {
    translate([0, -(inner_width/2 + wall + 1), 0]) {
        // Main clip body
        difference() {
            translate([-belt_clip_w/2, -belt_clip_depth, 0])
                cube([belt_clip_w, belt_clip_depth, inner_height + wall]);

            // Belt gap
            translate([-belt_clip_w/2 + 3, -belt_clip_depth + 2, inner_height + wall - belt_clip_gap - 8])
                cube([belt_clip_w - 6, belt_clip_depth, belt_clip_gap]);
        }
    }
}

module lid() {
    translate([0, 0, inner_height + wall + 5]) {  // Offset for display
        difference() {
            rounded_box(inner_length + wall*2, inner_width + wall*2,
                         wall, corner_r);

            // Vent slots matching body
            for (i = [0:vent_slots-1]) {
                x_pos = -inner_length/3 + i * (inner_length * 2/3) / (vent_slots - 1);
                translate([x_pos, 0, -0.1])
                    cube([3, inner_width * 0.6, wall + 0.2], center=true);
            }
        }

        // Lid engagement lip
        translate([0, 0, -lid_lip])
            difference() {
                rounded_box(inner_length - 0.4, inner_width - 0.4,
                             lid_lip, corner_r - wall/2 - 0.2);
                rounded_box(inner_length - wall, inner_width - wall,
                             lid_lip + 0.2, corner_r - wall);
            }
    }
}

// Assemble — box + belt clip + lid (offset above for printing)
box_body();
belt_clip();
lid();
