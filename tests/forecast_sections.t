use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/../scripts";
use Test::More;
use ForecastSections qw(extract_key_messages map_forecast_sections);

sub mapped_sections {
	my (@numbered_messages) = @_;
	my $discussion = 'KEY MESSAGES...overview&& DISCUSSION...';
	$discussion .= join ' ', map { "KEY MESSAGE $_: message-$_" } @numbered_messages;
	$discussion .= '&&';
	my $messages = extract_key_messages($discussion);
	return map_forecast_sections($messages);
}

is_deeply(
	extract_key_messages('KEY MESSAGES...overview&& DISCUSSION...KEY MESSAGE 1: first KEY MESSAGE 3: third&&'),
	{ 1 => 'first', 3 => 'third' },
	'extracts numbered discussion messages and ignores the overview',
);

is_deeply(
	mapped_sections(1, 2),
	{ synopsis => 'message-1', near_term => 'message-2', short_term => 'message-1', long_term => 'message-2' },
	'maps two messages to the low/high/low/high slots',
);

is_deeply(
	mapped_sections(1, 3),
	{ synopsis => 'message-1', near_term => 'message-3', short_term => 'message-1', long_term => 'message-3' },
	'maps two messages correctly when their numbers have a gap',
);

is_deeply(
	mapped_sections(1, 2, 3),
	{ synopsis => 'message-1', near_term => 'message-2', short_term => 'message-2', long_term => 'message-3' },
	'duplicates the middle message when three are available',
);

is_deeply(
	mapped_sections(1, 2, 3, 4),
	{ synopsis => 'message-1', near_term => 'message-2', short_term => 'message-3', long_term => 'message-4' },
	'maps four messages to the four slots',
);

is_deeply(
	mapped_sections(1, 2, 3, 4, 5),
	{ synopsis => 'message-1', near_term => 'message-2', short_term => 'message-4', long_term => 'message-5' },
	'anchors more than four messages to the sequence ends',
);

is_deeply(
	mapped_sections(7),
	{ synopsis => 'message-7', near_term => 'message-7', short_term => 'message-7', long_term => 'message-7' },
	'duplicates a single message into all four slots',
);

is_deeply(extract_key_messages('DISCUSSION...no numbered messages&&'), {}, 'returns no messages for an empty sequence');
is_deeply(map_forecast_sections({}), {}, 'returns no sections for an empty sequence');

done_testing();