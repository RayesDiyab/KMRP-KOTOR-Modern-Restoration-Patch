#!/usr/bin/env perl

# Copyright (C) 2017 ndix UR
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

use strict;
use Data::Dumper;
use File::Copy;
use File::Basename;
use IO::Handle;

my $DEBUG = 0;

sub usage {
  die sprintf("
Patch Knights of the Republic swkotor.exe for proper operation with rescaled UI.

usage: %s WIDTH HEIGHT LETTERBOX_SCALE EXECUTABLE

WIDTH is the horizontal resolution
HEIGHT is the vertical resolution
LETTERBOX_SCALE fix proportions yes | no (or true | false, 1 | 0) 
EXECUTABLE is the path to a writeable swkotor.exe file

",
    (split /[\/\\]/, $0)[-1]
  );
}

if (scalar(@ARGV) > 3) {
  # combine any space-containing filenames automatically as last argument
  @ARGV = (@ARGV[0,1,2], join(' ', @ARGV[3..scalar(@ARGV)]));
  $ARGV[3] =~ s/^\s+//;
  $ARGV[3] =~ s/\s+$//;
}
#print Dumper(\@ARGV);
usage() unless scalar(@ARGV) == 4;

#perl2exe_include bytes

my %opt = (
  width  => $ARGV[0],
  height => $ARGV[1],
  lbox   => $ARGV[2],
  path   => $ARGV[3],
);
my $config = {
  defaults  => {
    negative_offsets_x => -640,
    negative_offsets_y => -480,
    positive_offsets_x => 640,
    positive_offsets_y => 480,
    map_projection_offsets_x => 512,
    map_grid => 32,
    map_offsets_x => 440,
    map_offsets_y => 256,
    map_offsets_float_x => 440.0,
    map_offsets_float_y => 256.0,
  },
  dialog_offset_values => {
    # gog, 0.42857149
    gog => {
      #0x355788 => 0xB96DDB3E,
      0x355788 => 0x3EDB6DB9,
      # 4cd ITA
      0x34D340 => 0x3EDB6DB9,
      # 4cd POL
      0x3557A0 => 0x3EDB6DB9,
    },
    # mac, 2.33333333
    mac => {
      #0xCA6CC4 => 0x54551540,
      0xCA6CC4 => 0x40155554,
    }
  },
  negative_offsets_x => [
    [ 0xB6C7, 0xBA6C ], # gog
    [ 0xB537, 0xB8DC ], # 4cd ITA
    [ 0xB7B7, 0xBB5C ], # 4cd POL
  ],
  negative_offsets_y => [
    [ 0xB6DA, 0xBA83 ], # gog
    [ 0xB54A, 0xB8F3 ], # 4cd ITA
    [ 0xB7CA, 0xBB73 ], # 4cd POL
  ],
  positive_offsets_x => [
    [ 0xAA65, 0x292959, 0x2928B3 ], # gog
    [ 0xA895 ], # 4cd ITA
    [ 0xAB05 ], # 4cd POL
    [ 0xBD9424, 0xBD949B, 0xBDA055 ], # macOS
  ],
  positive_offsets_y => [
    [ 0xAA85, 0x29296B, 0x2928C3 ], # gog
    [ 0xA8B5 ], # 4cd ITA
    [ 0xAB25 ], # 4cd POL
    [ 0xBD9449, 0xBD94B3, 0xBDA06D], # macOS
  ],
  map_projection_offsets_x => [
    [ 0x29505C ],
  ],
  map_grid => [
    [ 0x17906F ],
  ],
  map_offsets_x => [
    [ 
      0x179009,
      0x179344, 0x179377, 0x17937E,
      0x178E9B, 
      0x178F15,
      0x295082,
      #0x347748, 440.0, not 440
    ],
  ],
  map_offsets_y => [
    [
      0x17901A,
      0x179358, 0x179383, 0x17938A,
      0x178EA6,
      0x178F24,
      0x295064,
      0x29508A,
      #0x3455D4, 256.0, not 256
    ],
  ],
  map_offsets_float_x => [
    [ 0x347748 ],
  ],
  map_offsets_float_y => [
    [ 0x3455D4 ],
  ],
};

if ($opt{width} !~ /^\d+$/) {
  printf("ERROR: %s is not a valid horizontal resolution\n", $opt{width});
  usage();
}
if ($opt{height} !~ /^\d+$/) {
  printf("ERROR: %s is not a valid vertical resolution\n", $opt{height});
  usage();
}
if (!-f $opt{path}) {
  printf("ERROR: file not found: %s\n", $opt{path});
  usage();
}
$opt{letterbox} = 1;
if ($opt{lbox} =~ /^(?:f|n|0)/i) {
  $opt{letterbox} = 0;
}
$opt{mapscale} = 0;

my ($fh, $buffer);
my $patch = {
  negative_offsets_x => [],
  negative_offsets_y => [],
  positive_offsets_x => [],
  positive_offsets_y => [],
  map_projection_offsets_x => [],
  map_offsets_x => [],
  map_offsets_y => [],
  map_offsets_float_x => [],
  map_offsets_float_y => [],
  dialog_letterbox => {},
};

# compute letterbox factors
my $letterbox_factors = {};
$letterbox_factors->{mac} = ($opt{width} / $opt{height}) * 1.75;
$letterbox_factors->{gog} = 1.0 / $letterbox_factors->{mac};
if ($opt{letterbox} &&
    ($opt{width} / $opt{height}) == (4.0 / 3.0)) {
  $opt{letterbox} = 0;
}

# search phase
if (!open($fh, '<', $opt{path})) {
  printf("ERROR: cannot open executable file for reading: %s\n", $opt{path});
  die sprintf("\nERROR: no modifications made, patch unsuccessful\n");
}
binmode($fh);
for my $offset_key ('negative_offsets_x',
                    'negative_offsets_y',
                    'positive_offsets_x',
                    'positive_offsets_y',
                    'map_projection_offsets_x',
                    'map_grid',
                    'map_offsets_x',
                    'map_offsets_y',
                    'map_offsets_float_x',
                    'map_offsets_float_y') {
  my $default_value = $config->{defaults}{$offset_key};
  for my $offsets (@{$config->{$offset_key}}) {
    if ($offset_key =~ /map_/ && !$opt{mapscale}) {
      next;
    }
    for my $offset (@{$offsets}) {
      seek($fh, $offset, 0);
      read($fh, $buffer, 4);
      my $tpl = 's';
      my $dbg = "%u : %d\n";
      if ($offset_key =~ /float/) {
        $tpl = 'f';
        $dbg = "%u (f) : %f\n";
      }
      my $test = unpack($tpl, $buffer);
      printf($dbg, $offset, $test) if $DEBUG;
      if ($test == $default_value) {
        push @{$patch->{$offset_key}}, $offset;
      }
    }
  }
}
# find patch for dialog letterbox mode
for my $offset_key (keys %{$config->{dialog_offset_values}}) {
  for my $offset (keys %{$config->{dialog_offset_values}{$offset_key}}) {
    my $default_value = $config->{dialog_offset_values}{$offset_key}{$offset};
    seek($fh, $offset, 0);
    read($fh, $buffer, 4);
    my $test = unpack('L', $buffer);
    printf("%u : %u\n", $offset, $test) if $DEBUG;
    printf("%u : %f\n", $offset, unpack('f', $buffer)) if $DEBUG;
    if ($test == $default_value) {
      $patch->{dialog_letterbox}{$offset_key} = [ $offset ];
    }
  }
}
if (!close($fh)) {
  printf("ERROR: cannot close executable file opened for reading: %s\n", $opt{path});
}

print Dumper($patch) if $DEBUG;

# test phase
my $tests_pass = 1;
if (scalar(@{$patch->{negative_offsets_x}}) < 2 &&
    scalar(@{$patch->{positive_offsets_x}}) < 3) {
  printf("\nERROR: did not find all negative x patch offsets\n");
  $tests_pass = 0;
}
if (scalar(@{$patch->{negative_offsets_y}}) < 2 &&
    scalar(@{$patch->{positive_offsets_y}}) < 3) {
  printf("\nERROR: did not find all negative y patch offsets\n");
  $tests_pass = 0;
}
if (scalar(@{$patch->{positive_offsets_x}}) < 1) {
  printf("\nERROR: did not find all positive x patch offsets\n");
  $tests_pass = 0;
}
if (scalar(@{$patch->{positive_offsets_y}}) < 1) {
  printf("\nERROR: did not find all positive y patch offsets\n");
  $tests_pass = 0;
}
if ($opt{letterbox} &&
    !scalar(keys %{$patch->{dialog_letterbox}})) {
  printf("\nERROR: did not find dialog letterbox patch offsets\n");
  $tests_pass = 0;
}
if (!open($fh, '+<', $opt{path})) {
  printf("ERROR: cannot open executable file for reading: %s\n", $opt{path});
  $tests_pass = 0;
}
if ($tests_pass) {
  printf("STEP 1: Tests passed, all patch offsets found, proceeding...\n");
} else {
  #die sprintf("\nERROR: no modifications made, patch unsuccessful\n");
}
#die;
# backup phase
my $backup_filename;
my $exe_path = dirname($opt{path});
my $exe_base = basename($opt{path}, '.exe');
my $is_exe = $opt{path} =~ /\.exe$/i;
for my $backup_stem ('', 00..20) {
  $backup_filename = sprintf('%s/%s.bak%s.exe', $exe_path, $exe_base, $backup_stem);
  if (!$is_exe) {
    # Mac version, XKOTOR file
    $backup_filename = sprintf('%s/%s-backup%s', $exe_path, $exe_base, $backup_stem);
  }
  if (-f $backup_filename) {
    if ($backup_stem eq "20") {
      die sprintf(
        "ERROR: too many backup files already exist, try removing one " .
        "or copying executable to new directory before patching...\n"
      );
    }
  } else {
    last;
  }
}
if (!copy($opt{path}, $backup_filename)) {
  printf("ERROR: cannot backup file to: %s\n", $backup_filename);
  die sprintf("\nERROR: no modifications made, patch unsuccessful\n");
}
printf("STEP 2: Backup file created: %s\n", $backup_filename);

# patch phase
printf("STEP 3: Patching executable: %s\n", $opt{path});
binmode($fh);
for my $offset_key ('negative_offsets_x',
                    'negative_offsets_y',
                    'positive_offsets_x',
                    'positive_offsets_y',
                    'map_projection_offsets_x',
                    'map_grid',
                    'map_offsets_x',
                    'map_offsets_y',
                    'map_offsets_float_x',
                    'map_offsets_float_y') {
  my $new_value = $opt{width};
  if ($offset_key =~ /_y$/) {
    $new_value = $opt{height};
  }
  if ($offset_key =~ /map/) {
    if (!$opt{mapscale}) {
      next;
    }
    $new_value = $opt{width} * (440.0 / 640.0); 
      $new_value = $opt{width} * (512.0 / 640.0); 
    if ($offset_key =~ /projection/) {
      $new_value = $opt{width} * (512.0 / 640.0); 
      #$new_value = $opt{width} * (440.0 / 640.0); 
    }
    if ($offset_key =~ /_y$/) {
      $new_value = $opt{height} * (256.0 / 480.0);
    }
    if ($offset_key =~ /_grid/) {
      #$new_value = 32 * (512.0 / 640.0); 
      $new_value = 32 * (($opt{height} * (256.0 / 480.0)) / 256.0);
      #$new_value *= 0.5;
    }
  }
  if ($offset_key =~ /negative/) {
    $new_value = 0 - $new_value;
  }
  my $tpl = 's';
  my $dbg = "%u : %d\n";
  if ($offset_key =~ /float/) {
    $tpl = 'f';
    $dbg = "%u (f) : %f\n";
  }
  for my $offset (@{$patch->{$offset_key}}) {
    printf($dbg, $offset, $new_value) if $DEBUG;
    seek($fh, $offset, 0);
    print $fh pack($tpl, $new_value);
  }
}
if ($opt{letterbox} && defined($patch->{dialog_letterbox})) {
  for my $offset_key (keys %{$patch->{dialog_letterbox}}) {
    for my $offset (@{$patch->{dialog_letterbox}{$offset_key}}) {
      printf(
        "%u : %f\n",
        $offset,
        $letterbox_factors->{$offset_key}
      ) if $DEBUG;
      seek($fh, $offset, 0);
      print $fh pack('f', $letterbox_factors->{$offset_key});
    }
  }
}
$fh->flush();
close($fh);
printf("Patch successful\n");
