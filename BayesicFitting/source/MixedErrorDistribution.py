import numpy as numpy
import math
import re
import sys

from .ErrorDistribution import ErrorDistribution
from .HyperParameter import HyperParameter
from .UniformPrior import UniformPrior
from . import Tools
from .Formatter import formatter as fmt

__author__ = "Do Kester"
__year__ = 2018
__license__ = "GPL3"
__version__ = "0.9"
__maintainer__ = "Do"
__status__ = "Development"

#  *
#  * This file is part of the BayesicFitting package.
#  *
#  * BayesicFitting is free software: you can redistribute it and/or modify
#  * it under the terms of the GNU Lesser General Public License as
#  * published by the Free Software Foundation, either version 3 of
#  * the License, or ( at your option ) any later version.
#  *
#  * BayesicFitting is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU Lesser General Public License for more details.
#  *
#  * The GPL3 license can be found at <http://www.gnu.org/licenses/>.
#  *
#  *    2018        Do Kester


class MixedErrorDistribution( ErrorDistribution ):
    """
    To calculate a mixture of two likelihoods.

    For one residual, x, it holds
    .. math::
        L( x ) = f * L1( x ) + ( 1 - f ) * L2( x )

    where f is the contributing fraction while L, L1 and L2 are likelihoods
    f is a hyperparameter between [0..1]

    The likelihood over N datapoints is
    .. math::
        L = \Pi{ L( x ) } = \Pi{ f * L1( x ) + ( 1 - f ) * L2( x ) }

    And the log of L is
    .. math::
        logL = \Sum{ logL( x ) } = \Sum{ log( f * L1(x) + ( 1 - f ) * L2(x) ) }

    Author       Do Kester.

    """

    #  *********CONSTRUCTORS***************************************************
    def __init__( self, errdis1, errdis2, fraction=0.5, limits=None, copy=None ):
        """
        Constructor.

        Make a new error distribution as a fraction of errdis1 plus the rest of errdis2.

        Parameters
        ----------
        errdis1 : ErrorDistribution
            First error distribution
        errdis2 : ErrorDistribution
            Second error distribution (might be of the same class as errdis1)
            It *must* have the same xdata, data, weights as errdis1.
        fraction : float
            contributing fraction
        limits : None or list of 2 floats [low,high]
            None : no limits implying fixed fraction
            low     low limit on fraction ( >0)
            high    high limit on fraction ( <1)
            when limits are set, the scale is *not* fixed.

        copy : MixedErrorDistribution
            distribution to be copied.

        """
        super( MixedErrorDistribution, self ).__init__( errdis1.xdata, errdis1.data,
                    weights=errdis1.weights, copy=copy )

        self.errdis1 = errdis1
        self.errdis2 = errdis2
        if copy is None :
            self.hyperpar = errdis1.hyperpar + errdis2.hyperpar
            fprior = UniformPrior( )
            fraction = HyperParameter( hypar=fraction, prior=fprior, limits=limits )
            self.hyperpar += [fraction]

    def copy( self ):
        """ Return copy of this.  """
        return MixedErrorDistribution( self.errdis1, self.errdis2, copy=self )

    def __setattr__( self, name, value ):
        """
        Set attributes.

        """
        key1 = {"errdis1": ErrorDistribution, "errdis2" : ErrorDistribution }

        if Tools.setSingleAttributes( self, name, value, key1 ) :
            pass
        else :
            super( MixedErrorDistribution, self ).__setattr__( name, value )


    def acceptWeight( self ):
        """
        True if the distribution accepts weights.
        Always true for this distribution.
        """
        return self.errdis1.acceptWeight() and self.errdis2.acceptWeight()


    #  *********LIKELIHOODS***************************************************
    def logLdata( self, model, allpars, mockdata=None ) :
        """
        Return the log( likelihood ) for a Mixedian distribution.

        Parameters
        ----------
        model : Model
            to be fitted
        allpars : array_like
            list of all parameters in the problem
        mockdata : array_like
            as calculated by the model

        """
        if mockdata is None :
            mockdata = model.result( self.xdata, allpars[:model.npchain] )

        f = allpars[-1]
        n1 = self.errdis1.nphypar
        n2 = self.errdis2.nphypar
        p1 = allpars[:-n2-1]
        p2 = allpars[:-n1-1].copy()
        p2[-n2:] = allpars[-n2-1:-1]

        if f <= 0 :
            return self.errdis2.logLdata( model, p2, mockdata=mockdata )
        if f >= 1 :
            return self.errdis1.logLdata( model, p1, mockdata=mockdata )

        return numpy.logaddexp(
                self.errdis1.logLdata( model, p1, mockdata=mockdata ) + math.log( f ),
                self.errdis2.logLdata( model, p2, mockdata=mockdata ) + math.log( 1 - f ) )

    def nextPartialData( self, model, allpars, fitIndex, mockdata=None ) :
        """
        Return the partial derivative of log( likelihood ) to the parameters in fitIndex.

        Parameters
        ----------
        model : Model
            to be fitted
        allpars : array_like
            parameters of the problem
        fitIndex : array_like
            indices of parameters to be fitted
        mockdata : array_like
            as calculated by the model

        """
        if mockdata is None :
            mockdata = model.result( self.xdata, allpars[:model.npchain] )

        # make allpars lists (p1,p2)for errdis1&2; shift hyperpars in p2
        f = allpars[-1]
        emf = 1 - f
        n1 = self.errdis1.nphypar
        n2 = self.errdis2.nphypar
        p1 = allpars[:-n2-1]
        p2 = allpars[:-n1-1].copy()
        p2[-n2:] = allpars[-n2-1:-1]


        # make fitIndex (f1,f2) for errdis1&2
        fitIndex = numpy.asarray( fitIndex )
        q = numpy.where( fitIndex >= 0 )
        f1 = fitIndex[q]
        f2 = f1.copy()
        if -3 in fitIndex :
            f1 = numpy.append( f1, [-1] )
        if -2 in fitIndex :
            f2 = numpy.append( f2, [-1] )

        # make fitindices (f1,f2) for errdis1&2
        lhd1 = numpy.exp( self.errdis1.logLdata( model, p1, mockdata=mockdata ) )
        lhd2 = numpy.exp( self.errdis2.logLdata( model, p2, mockdata=mockdata ) )
        pg1 = self.errdis1.nextPartialData( model, p1, f1, mockdata=mockdata )
        pg2 = self.errdis2.nextPartialData( model, p2, f2, mockdata=mockdata )

#        q1 = numpy.where( numpy.logical_not( numpy.isfinite( lhd1 ) ) )[0]
#        q2 = numpy.where( numpy.logical_not( numpy.isfinite( lhd2 ) ) )[0]

#        print( q1, len( q1 ) )
#        print( lhd1[q1] )
#        print( q2, len( q2 ) )
#        print( lhd2[q2] )

        ff1 = f * lhd1 + emf * lhd2
        # Where the mixed likelihood (=ff1) is indistinguishable from 0,
        # its partials also must be zero. In those locations we can replace
        # the inverse of ff1, needed in calculating the partials, by 0.

        fff = numpy.where( ff1 < sys.float_info.min, 0.0, 1.0 / ff1 )


#        q1 = numpy.where( numpy.logical_not( numpy.isfinite( fff ) ) )[0]
#        print( "fff  ", q1, len( q1 ) )
#        print( fff[q1] )
#        print( ff1[q1] )
#        print( "MED1  ", f, emf, numpy.all( numpy.isfinite( fff ) ) )

        for fi in fitIndex :
#            print( "MED2  ", fi )
            if fi >= 0 :            ## partialLogL for model parameters
                npg1 = next( pg1 )
                npg2 = next( pg2 )

#                q1 = numpy.where( numpy.logical_not( numpy.isfinite( npg1 ) ) )[0]
#                print( "NPG1  ", fi, q1, len( q1 ) )
#                print( npg1[q1] )

#                q2 = numpy.where( numpy.logical_not( numpy.isfinite( npg2 ) ) )[0]
#                print( "NPG2  ", fi, q2, len( q2 ) )
#                print( npg2[q2] )

                yield ( fff * ( f * lhd1 * npg1 +
                              emf * lhd2 * npg2 ) )
#                yield ( fff * ( f * lhd1 * next( pg1 ) +
#                              emf * lhd2 * next( pg2 ) ) )

            if fi == -1 :           ## partialLogL for fraction f
                yield ( ( lhd1 - lhd2 ) * fff )

            elif fi == -2 :         ## partialLogL for sigma of errdis2
                npg2 = next( pg2 )
#                q2 = numpy.where( numpy.logical_not( numpy.isfinite( npg2 ) ) )[0]
#                print( "NPG2  ", fi, q2, len( q2 ) )
#                print( npg2[q2] )

                yield ( emf * lhd2 * fff * npg2 )
#                yield ( emf * lhd2 * fff * next( pg2 ) )

            elif fi == -3 :         ## partialLogL for sigma of errdis1
                npg1 = next( pg1 )
#                q1 = numpy.where( numpy.logical_not( numpy.isfinite( npg1 ) ) )[0]
#                print( "NPG1  ", fi, q1, len( q1 ) )
#                print( npg1[q1] )

                yield ( f * lhd1 * fff * npg1 )
#                yield ( f * lhd1 * fff * next( pg1 ) )

        try :
            pg1.close()
            pg2.close()
        except :
            pass
        return

    def __str__( self ) :
        n1 = re.match( "^[a-zA-Z_]*", self.errdis1.__str__() ).group(0)
        n2 = re.match( "^[a-zA-Z_]*", self.errdis2.__str__() ).group(0)
        return "Mixed error distribution : %s + %s" % (n1, n2)
