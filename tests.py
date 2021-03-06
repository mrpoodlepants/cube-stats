#!/usr/bin/python2
"""Unit tests for cube-stats."""

import sys
import unittest
import cStringIO

import setup
import draft
import trollconvert

db = None  # Set by configDB

# The cards file currently has 6 lines, 1 duplicate (Swamp), and ends in a newline character.
cards_file = "test_support/test_cardlist.txt"
cards_file2 = "test_support/test_cardlist2.txt"

# Sample draft reports for use in conjunction with cards_file
draft_file = "test_support/test_draft_report.txt"
draft_file_err = "test_support/test_draft_report_err.txt"
draft_file_err2 = "test_support/test_draft_report_err2.txt"

# Files for trollitaire draft conversion

old_troll_file = "test_support/example_old_style_troll.draft"
old_troll_file2 = "test_support/example_old_style_troll2.draft"
converted_troll = "test_support/example_troll_converted.draft"
converted_troll2 = "test_support/example_troll_converted2.draft"


def getTempDB(showerr=False):
    """Create temp database by manually executing db setup code."""
    from dal import DAL, Field
    import tempfile
    
    with open('common.py', 'r') as f:
        filelines = f.readlines()

    # Parses db setup module into text, makes a change, & executes code.
    codelines = []
    curline = ""
    for line in filelines:
        line = line.strip()
        if "DAL(" in line:
            # Modify the db path to be in a temp folder
            # Replacing backslashes b/c windoze
            line = line[:line.find('folder')] + " folder=\"" + tempfile.gettempdir().replace("\\", "/") + "\")"
        if len(line) == 0:
            continue
        elif line[0] == "#":
            continue
        else:
            # Join line continuations
            curline += line
            if curline[-1] != "," and curline[-1] != "(":
                codelines.append(curline)
                curline = ""

    for line in codelines:
        try:
            exec(line) in globals(), locals()
        except:
            if showerr:
                print 'err', line

    return db

    
class MainTest(unittest.TestCase):

    """Unit tests for cube-stats. Includes setup of db and calculation of stuff. """

    def setUp(self):
        """do stuff to prepare for each test"""
        for table in setup.db.tables:
            setup.db[table].truncate("CASCADE")
        
    def tearDown(self):
        """do stuff to clean up after each test"""
        pass
        
    def testLoadCardList(self):
        """test that loading a test list of cards to an empty database works"""
        # cards_file has 5 cards (6 lines and a duplicate swamp)
        setup.update(cards_file)
        
        cards = setup.db(setup.db.Cards.id > 0).select()
        self.assertEqual(len(cards), 5)
        
        swamp = setup.db(setup.db.Cards.Name == "Swamp").select().first()
        self.assertEqual(swamp.Quantity, 2)
    
        # Ensure the rest are active w/ quantity 1
        for card in cards:
            if card.Name != "Swamp":
                self.assertEqual(card.Quantity, 1)

    def testUpdateCardList(self):
        """test that database is updated properly"""
        setup.update(cards_file)  # Tested via testLoadCardList
        setup.update(cards_file2)
        
        # cards_list2 should make the following changes against card_list:
        # - 1x Swamp
        # - 1x Faith's Fetters
        # + 1x Island
        cards = setup.db(setup.db.Cards.id > 0).select()

        ff = setup.db(setup.db.Cards.Name == "Faith's Fetters")
        self.assertEqual(ff.count(), 1)

        self.assertEqual(1, setup.db(setup.db.Cards.Name == "Swamp").select().first().Quantity)
        self.assertEqual(0, setup.db(setup.db.Cards.Name == "Faith's Fetters").select().first().Quantity)
        self.assertEqual(1, setup.db(setup.db.Cards.Name == "Island").select().first().Quantity)

    def testNewCardRatings(self):
        """test that cards with no transactions can be loaded from the db"""
        setup.update(cards_file) # Tested via testLoadCardList
        setup.update(cards_file2) # Tested via testUpdateCardList
        ratings = draft.get_current_ratings()

        # Do get all active cards (Qty != 0)
        self.assertEqual(len(ratings), 5)

        # Do not get any inactive cards (Qty == 0)
        self.assertTrue("Faith's Fetters" not in ratings)

        # No transactions yet; check that all mu,sigma are (25.0,25.0/3)
        for entry in ratings.values():
            self.assertAlmostEqual(entry[0], 25.0)
            self.assertAlmostEqual(entry[1], 25.0/3)

    def testPartialUpdateCoeffs(self):
        """verify that update coeffs are created correctly for n>0 deals."""
        t = draft.Trollitaire()

        self.assertRaises(ValueError, t.generate_partial_update_coeffs, 'a')
        self.assertRaises(ValueError, t.generate_partial_update_coeffs, 0)

        for x in range(1, 150):
            a = t.generate_partial_update_coeffs(x)
            self.assertEqual(len(a), x) # Critical - len(list) == num_deals.
            self.assertAlmostEqual(a[0], 1.0) # First deal is always 1.0.
            if x > 1: # Check that the last element is 0.1 for >1 deal.
                self.assertAlmostEqual(a[-1], 0.1)
            if x == 11: # Check an arbitrary point on the line for 11 deals.
                self.assertAlmostEqual(a[5], 0.6)
            if x == 21: # Check anther arbitrary point at x = 21.
                self.assertAlmostEqual(a[7], 0.75)

    def testTrollitaireDeal(self):
        """Test that a Trollitaire deal can be correctly processed.""" 
        t = draft.Trollitaire()

        _M = 25.0
        _S = 25.0/3
        dummycards = {'Ow':(_M,_S), 'Ice':(_M,_S), 'Mox':(_M,_S), 'Tek':(_M,_S),
                      'Discombobulate':(_M,_S)}
        dummyplacement = {'Ow':0, 'Ice':1, 'Mox':2, 'Tek':2, 'Discombobulate':2}

        result = t.process_deal(dummycards, dummyplacement)

        self.assertAlmostEqual(result['Ow'][0], 8.52939199)
        self.assertAlmostEqual(result['Ice'][0], 2.00, places = 4)
        self.assertAlmostEqual(result['Discombobulate'][1], -3.1, places = 1)

    def testTrollitaireDraft(self):
        '''this mostly just tests that process_deal doesn't throw errors.'''
        # TODO add validation of deal data against the ratings dictionary
        pass
    
        # make better later
        t = draft.Trollitaire()
        a = {ch:(25.0,25.0/3) for ch in 'abcdefg'}
        b = [{ch:i for ch, i in zip('abcde', [0,1,2,2,2])}]

        r = t.process_draft(a,b)
        
        self.assertAlmostEqual(r['b'][0], 27.00, places=2) # Check a mu value
        self.assertAlmostEqual(r['a'][1], 6.193347454688) # Check a sigma value

    def testDraftFileParsing(self):
        """Test that a properly formatted file can be read and parsed into a
        list of deals. Also verify that appropriate errors are thrown for mal-
        formed input, and that [UNDO] tags are handled smoothly as well.

        parse_report_file will not verify that the cards listed are spelled
        correctly or even in the cube - that will be the responsibility of
        process_draft.
        """

        # Picks should be:
        draft_file_output = [
            {'Glare of Subdual':0, 'Swamp':1, "Faith's Fetters":2, "Lightning Helix":2},
            {'Aether Vial':0, 'Lightning Helix':1, "Faith's Fetters":1, 'Swamp':1},
            {'Swamp':0, 'Aether Vial':1, 'Glare of Subdual':1, 'Lightning Helix':1} ]
        
        t = draft.Trollitaire()
        out = t.parse_report_file(draft_file)

        # Slightly more detailed error reporting than simply comparing the outputs equal
        self.assertEqual(len(out), len(draft_file_output))
        for i in range(len(out)):
            self.assertEqual(out[i], draft_file_output[i])

    def testDraftFileErrorChecks(self):
        """Test that draft files with errors in them generate the appropriate
        exceptions."""

        t = draft.Trollitaire()
        # Change from ValueError to whatever makes sense
        self.assertRaises(ValueError, t.parse_report_file, draft_file_err)
        self.assertRaises(ValueError, t.parse_report_file, draft_file_err2)

    def testDraftFileWarningChecks(self):
        """test that [UNDO] lines and other non-fatal anomalies generate
        appropriate warning messages."""

        #TODO implement this - how to handle checks of log functions?
        pass
    
    def testTransactionWrite(self):
        """Test that transactions can be written to the db correctly."""
        setup.update(cards_file)
        draft.db = setup.db
        trans = {'Swamp':(23.2,6.55), "Faith's Fetters":(11.9,4.33)}
        
        draft.write_updated_ratings(trans)

        ratings = draft.get_current_ratings()

        for card in trans:
            self.assertEqual(trans[card], ratings[card])

    def testTrollitaireConverter(self):
        """Test that the Trollitaire converter works properly."""
        # First test case (no surprises)
        tempfile = cStringIO.StringIO()
        with open(old_troll_file) as infile:
            trollconvert.convert_draft_file(infile, tempfile)

        expected = open(converted_troll).read()
        tempfile.seek(0)
        result = tempfile.read()
        self.assertEqual(expected, result)

        # Second test case (has an UNDO)
        tempfile = cStringIO.StringIO()
        with open(old_troll_file2) as infile:
            trollconvert.convert_draft_file(infile, tempfile)

        expected = open(converted_troll2).read()
        tempfile.seek(0)
        result = tempfile.read()
        self.assertEqual(expected, result)

if __name__ == "__main__":
    setup.db = draft.db = getTempDB(showerr=True)
    unittest.main()
