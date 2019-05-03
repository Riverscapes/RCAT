# -------------------------------------------------------------------------------
# Name:        StreamObjects
# Purpose:     This file holds classes that will be used to hold data in RCAT tools
#
# Author:      Braden Anderson
#
# Created:     03/2018
# -------------------------------------------------------------------------------

import heapq


class DAValueCheckStream:
    def __init__(self, reach_id,  stream_id, downstream_dist, drainage_area):
        self.reach_id = reach_id
        self.stream_id = stream_id
        self.downstream_dist = downstream_dist
        self.drainage_area = drainage_area

    def __eq__(self, other):
        return self.reach_id == other.reach_id

    def __lt__(self, other):
        """
        The heap is based on downstream distance, so we define < and > based on downstream distance

        To make the heap a max heap, we reverse what might seem to be intuitive for > and <. To make it a min heap,
        replace ">" with "<" in the return statement
        """
        if not isinstance(other, DAValueCheckStream):
            raise Exception("Comparing a DAValueCheckStream to another data type is not currently supported")
        return self.downstream_dist > other.downstream_dist

    def __gt__(self, other):
        """
        The heap is based on downstream distance, so we define < and > based on downstream distance

        To make the heap a max heap, we reverse what might seem to be intuitive for > and <. To make it a min heap,
        replace "<" with ">" in the return statement
        """
        if not isinstance(other, DAValueCheckStream):
            raise Exception("Comparing a DAValueCheckStream to another data type is not currently supported")
        return self.downstream_dist < other.downstream_dist

    def __str__(self):
        return str(self.stream_id)


class ProblemStream:
    def __init__(self, reach_id, stream_id, orig_drainage_area, fixed_drainage_area):
        self.reach_id = reach_id
        self.stream_id = stream_id
        self.orig_drainage_area = orig_drainage_area
        self.fixed_drainage_area = fixed_drainage_area

    def __str__(self):
        ret_string = 'Reach_ID: ' + str(self.reach_id)
        ret_string += 'Stream_ID: ' + str(self.stream_id)
        ret_string += '\nOriginal Drainage Area: ' + str(self.orig_drainage_area)
        ret_string += '\nFixed Drainage Area: ' + str(self.fixed_drainage_area) + '\n\n'

        return ret_string


class StreamHeap:
    def __init__(self, first_stream):
        self.streams = [first_stream]
        self.stream_id = first_stream.stream_id

    def push_stream(self, given_stream):
        heapq.heappush(self.streams, given_stream)

    def pop(self):
        return heapq.heappop(self.streams)

    def first_element(self):
        if len(self.streams) > 0:
            return self.streams[0]
        else:
            return None

    def __eq__(self, other):
        if not isinstance(other, StreamHeap):
            raise Exception("A StreamHeap can only be compared to another StreamHeap")
        return self.stream_id == other.stream_id

    def __str__(self):
        ret_string = '['
        for i in range(len(self.streams)):
            #ret_string += '(' + str(self.streams[i].reach_id) + ', ' + str(self.streams[i].stream_id) + ')'
            ret_string += str(self.streams[i].downstream_dist)
            if i + 1 < len(self.streams):
                ret_string += ', '
        ret_string += ']'
        return ret_string